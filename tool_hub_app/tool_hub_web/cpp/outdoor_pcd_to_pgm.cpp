#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs = std::filesystem;

struct Point { double x, y, z; };
struct Options {
  fs::path input;
  fs::path trajectory;
  fs::path output_dir;
  std::string map_name = "outdoor_map";
  double z_min = 0.0;
  double z_max = 0.4;
  double radius = 0.5;
  int min_neighbors = 10;
  double resolution = 0.05;
  double sensor_height = 0.5;
  double trajectory_search_radius = 30.0;
  int preview_max_dimension = 0;
  int threads = 0;
  bool negative = false;
};

struct PcdHeader {
  std::vector<std::string> fields;
  std::vector<int> sizes;
  std::vector<char> types;
  std::vector<int> counts;
  std::size_t points = 0;
  std::size_t data_offset = 0;
  std::string data_type;
};

struct Result {
  int width = 1;
  int height = 1;
  int preview_width = 1;
  int preview_height = 1;
  std::size_t raw_count = 0;
  std::size_t filtered_count = 0;
  double x_min = 0.0;
  double y_min = 0.0;
  fs::path preview_pgm;
  fs::path pgm;
  fs::path yaml;
};

static std::vector<std::uint8_t> read_file(const fs::path & path)
{
  std::ifstream file(path, std::ios::binary);
  if (!file) throw std::runtime_error("cannot open PCD: " + path.string());
  file.seekg(0, std::ios::end);
  const auto size = static_cast<std::size_t>(file.tellg());
  file.seekg(0);
  std::vector<std::uint8_t> bytes(size);
  file.read(reinterpret_cast<char *>(bytes.data()), static_cast<std::streamsize>(size));
  return bytes;
}

static std::string lower(std::string value)
{
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return value;
}

static PcdHeader parse_header(const std::vector<std::uint8_t> & bytes)
{
  PcdHeader header;
  std::size_t cursor = 0;
  while (cursor < bytes.size()) {
    const std::size_t line_end = std::find(bytes.begin() + static_cast<std::ptrdiff_t>(cursor), bytes.end(), '\n') - bytes.begin();
    std::string line(reinterpret_cast<const char *>(bytes.data() + cursor), line_end - cursor);
    if (!line.empty() && line.back() == '\r') line.pop_back();
    cursor = line_end < bytes.size() ? line_end + 1 : bytes.size();
    std::istringstream stream(line);
    std::string key;
    stream >> key;
    key = lower(key);
    if (key == "fields") { for (std::string value; stream >> value;) header.fields.push_back(value); }
    else if (key == "size") { for (int value; stream >> value;) header.sizes.push_back(value); }
    else if (key == "type") { for (char value; stream >> value;) header.types.push_back(value); }
    else if (key == "count") { for (int value; stream >> value;) header.counts.push_back(value); }
    else if (key == "points") { stream >> header.points; }
    else if (key == "width" && header.points == 0) { std::size_t width; stream >> width; header.points = width; }
    else if (key == "data") { stream >> header.data_type; header.data_type = lower(header.data_type); header.data_offset = cursor; break; }
  }
  if (header.fields.empty() || header.sizes.size() != header.fields.size() || header.types.size() != header.fields.size()) {
    throw std::runtime_error("invalid PCD header");
  }
  if (header.counts.empty()) header.counts.assign(header.fields.size(), 1);
  return header;
}

static int field_index(const PcdHeader & header, const std::string & name)
{
  auto it = std::find(header.fields.begin(), header.fields.end(), name);
  if (it == header.fields.end()) throw std::runtime_error("PCD is missing field " + name);
  return static_cast<int>(it - header.fields.begin());
}

static std::size_t field_offset(const PcdHeader & header, int target)
{
  std::size_t offset = 0;
  for (int index = 0; index < target; ++index) offset += static_cast<std::size_t>(header.sizes[index] * header.counts[index]);
  return offset;
}

static std::uint32_t read_u32(const std::uint8_t * data)
{
  return static_cast<std::uint32_t>(data[0]) |
         (static_cast<std::uint32_t>(data[1]) << 8) |
         (static_cast<std::uint32_t>(data[2]) << 16) |
         (static_cast<std::uint32_t>(data[3]) << 24);
}

static std::vector<std::uint8_t> lzf_decompress(const std::uint8_t * data, std::size_t size, std::size_t expected)
{
  std::vector<std::uint8_t> output;
  output.reserve(expected);
  std::size_t cursor = 0;
  while (cursor < size) {
    const std::uint8_t control = data[cursor++];
    if (control < 32) {
      const std::size_t length = static_cast<std::size_t>(control) + 1;
      if (cursor + length > size) throw std::runtime_error("truncated LZF literal");
      output.insert(output.end(), data + cursor, data + cursor + length);
      cursor += length;
      continue;
    }
    std::size_t length = control >> 5;
    std::size_t reference_offset = static_cast<std::size_t>(control & 0x1f) << 8;
    if (length == 7) {
      if (cursor >= size) throw std::runtime_error("truncated LZF length");
      length += data[cursor++];
    }
    if (cursor >= size) throw std::runtime_error("truncated LZF reference");
    reference_offset += data[cursor++];
    length += 2;
    if (reference_offset + 1 > output.size()) throw std::runtime_error("invalid LZF reference");
    std::size_t reference = output.size() - reference_offset - 1;
    for (std::size_t index = 0; index < length; ++index) output.push_back(output[reference++]);
  }
  if (output.size() != expected) throw std::runtime_error("LZF output size mismatch");
  return output;
}

static double read_scalar(const std::uint8_t * data, int size, char type)
{
  if (type == 'F' && size == 4) { float value; std::memcpy(&value, data, 4); return value; }
  if (type == 'F' && size == 8) { double value; std::memcpy(&value, data, 8); return value; }
  throw std::runtime_error("unsupported PCD scalar type");
}

static std::vector<Point> load_points(const fs::path & path)
{
  const auto bytes = read_file(path);
  const auto header = parse_header(bytes);
  const int xi = field_index(header, "x");
  const int yi = field_index(header, "y");
  const int zi = field_index(header, "z");
  std::vector<Point> points(header.points);

  if (header.data_type == "ascii") {
    std::string text(reinterpret_cast<const char *>(bytes.data() + header.data_offset), bytes.size() - header.data_offset);
    std::istringstream stream(text);
    for (std::size_t index = 0; index < header.points; ++index) {
      std::vector<double> values(header.fields.size());
      for (double & value : values) stream >> value;
      points[index] = {values[xi], values[yi], values[zi]};
    }
    return points;
  }

  std::vector<std::uint8_t> data;
  if (header.data_type == "binary_compressed") {
    if (bytes.size() < header.data_offset + 8) throw std::runtime_error("truncated compressed PCD");
    const auto compressed_size = read_u32(bytes.data() + header.data_offset);
    const auto uncompressed_size = read_u32(bytes.data() + header.data_offset + 4);
    const auto * compressed = bytes.data() + header.data_offset + 8;
    data = lzf_decompress(compressed, compressed_size, uncompressed_size);
    const auto x_offset = field_offset(header, xi) * header.points;
    const auto y_offset = field_offset(header, yi) * header.points;
    const auto z_offset = field_offset(header, zi) * header.points;
    for (std::size_t index = 0; index < header.points; ++index) {
      points[index] = {
        read_scalar(data.data() + x_offset + index * header.sizes[xi], header.sizes[xi], header.types[xi]),
        read_scalar(data.data() + y_offset + index * header.sizes[yi], header.sizes[yi], header.types[yi]),
        read_scalar(data.data() + z_offset + index * header.sizes[zi], header.sizes[zi], header.types[zi])};
    }
    return points;
  }

  if (header.data_type == "binary") {
    std::size_t point_step = 0;
    for (std::size_t index = 0; index < header.fields.size(); ++index) point_step += header.sizes[index] * header.counts[index];
    for (std::size_t index = 0; index < header.points; ++index) {
      const auto * point = bytes.data() + header.data_offset + index * point_step;
      points[index] = {
        read_scalar(point + field_offset(header, xi), header.sizes[xi], header.types[xi]),
        read_scalar(point + field_offset(header, yi), header.sizes[yi], header.types[yi]),
        read_scalar(point + field_offset(header, zi), header.sizes[zi], header.types[zi])};
    }
    return points;
  }
  throw std::runtime_error("unsupported PCD DATA type: " + header.data_type);
}

struct Cell { int x, y; bool operator==(const Cell & other) const { return x == other.x && y == other.y; } };
struct CellHash { std::size_t operator()(const Cell & cell) const { return (static_cast<std::size_t>(static_cast<std::uint32_t>(cell.x)) << 32) ^ static_cast<std::uint32_t>(cell.y); } };

static Cell xy_cell(double x, double y, double origin_x, double origin_y, double resolution)
{
  return {static_cast<int>(std::floor((x - origin_x) / resolution)), static_cast<int>(std::floor((y - origin_y) / resolution))};
}

static std::unordered_map<Cell, double, CellHash> build_floor_values(
  const std::vector<Point> & points, const std::vector<Point> & trajectory,
  double origin_x, double origin_y, double resolution, double sensor_height,
  double search_radius, double & fallback_floor)
{
  fallback_floor = 0.0;
  if (trajectory.empty()) return {};
  for (const auto & point : trajectory) fallback_floor += point.z;
  fallback_floor = fallback_floor / trajectory.size() - sensor_height;

  std::unordered_map<Cell, int, CellHash> cell_ids;
  std::vector<Cell> cells;
  for (const auto & point : points) {
    const Cell cell = xy_cell(point.x, point.y, origin_x, origin_y, resolution);
    if (cell_ids.emplace(cell, static_cast<int>(cells.size())).second) cells.push_back(cell);
  }

  const double search_cell_size = search_radius;
  std::unordered_map<Cell, std::vector<int>, CellHash> trajectory_grid;
  for (int index = 0; index < static_cast<int>(trajectory.size()); ++index) {
    const Cell cell = {
      static_cast<int>(std::floor(trajectory[index].x / search_cell_size)),
      static_cast<int>(std::floor(trajectory[index].y / search_cell_size))};
    trajectory_grid[cell].push_back(index);
  }
  std::vector<double> values(cells.size(), fallback_floor);
#pragma omp parallel for schedule(dynamic)
  for (int index = 0; index < static_cast<int>(cells.size()); ++index) {
    const double query_x = origin_x + (cells[index].x + 0.5) * resolution;
    const double query_y = origin_y + (cells[index].y + 0.5) * resolution;
    const Cell search_cell = {
      static_cast<int>(std::floor(query_x / search_cell_size)),
      static_cast<int>(std::floor(query_y / search_cell_size))};
    double weight_sum = 0.0;
    double z_sum = 0.0;
    for (int dx = -1; dx <= 1; ++dx) for (int dy = -1; dy <= 1; ++dy) {
      const auto it = trajectory_grid.find({search_cell.x + dx, search_cell.y + dy});
      if (it == trajectory_grid.end()) continue;
      for (const int trajectory_index : it->second) {
        const double ddx = trajectory[trajectory_index].x - query_x;
        const double ddy = trajectory[trajectory_index].y - query_y;
        const double distance_squared = ddx * ddx + ddy * ddy;
        if (distance_squared > search_radius * search_radius) continue;
        const double weight = 1.0 / (distance_squared + 1e-6);
        weight_sum += weight;
        z_sum += weight * trajectory[trajectory_index].z;
      }
    }
    if (weight_sum > 0.0) values[index] = z_sum / weight_sum - sensor_height;
  }

  std::unordered_map<Cell, double, CellHash> result;
  result.reserve(cells.size());
  for (std::size_t index = 0; index < cells.size(); ++index) result[cells[index]] = values[index];
  return result;
}

static std::vector<Point> radius_filter(
  const std::vector<Point> & points, double radius, int min_neighbors)
{
  if (points.empty() || radius <= 0.0 || min_neighbors <= 0) return points;
  std::unordered_map<Cell, std::vector<int>, CellHash> grid;
  for (int index = 0; index < static_cast<int>(points.size()); ++index) {
    grid[{static_cast<int>(std::floor(points[index].x / radius)), static_cast<int>(std::floor(points[index].y / radius))}].push_back(index);
  }
  std::vector<std::uint8_t> keep(points.size(), 0);
  const double radius_squared = radius * radius;
#pragma omp parallel for schedule(static)
  for (int index = 0; index < static_cast<int>(points.size()); ++index) {
    const Cell cell = {
      static_cast<int>(std::floor(points[index].x / radius)),
      static_cast<int>(std::floor(points[index].y / radius))};
    int neighbors = 0;
    for (int dx = -1; dx <= 1 && neighbors < min_neighbors; ++dx) for (int dy = -1; dy <= 1 && neighbors < min_neighbors; ++dy) {
      const auto it = grid.find({cell.x + dx, cell.y + dy});
      if (it == grid.end()) continue;
      for (const int other_index : it->second) {
        const double ddx = points[other_index].x - points[index].x;
        const double ddy = points[other_index].y - points[index].y;
        const double ddz = points[other_index].z - points[index].z;
        if (ddx * ddx + ddy * ddy + ddz * ddz <= radius_squared) ++neighbors;
        if (neighbors >= min_neighbors) break;
      }
    }
    if (neighbors >= min_neighbors) keep[index] = 1;
  }
  std::vector<Point> filtered;
  filtered.reserve(points.size());
  for (std::size_t index = 0; index < points.size(); ++index) if (keep[index]) filtered.push_back(points[index]);
  return filtered;
}

static std::vector<std::uint8_t> render_pgm(int width, int height, const std::vector<std::uint8_t> & occupancy)
{
  std::vector<std::uint8_t> output;
  const std::string header = "P5\n" + std::to_string(width) + " " + std::to_string(height) + "\n255\n";
  output.insert(output.end(), header.begin(), header.end());
  for (int row = height - 1; row >= 0; --row) {
    for (int col = 0; col < width; ++col) output.push_back(occupancy[col + row * width] >= 100 ? 0 : 254);
  }
  return output;
}

static void write_pgm(const fs::path & path, int width, int height, const std::vector<std::uint8_t> & occupancy)
{
  const auto bytes = render_pgm(width, height, occupancy);
  std::ofstream file(path, std::ios::binary);
  file.write(reinterpret_cast<const char *>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
}

static void write_trajectory_overlay_ppm(
  const fs::path & path,
  int width,
  int height,
  const std::vector<std::uint8_t> & occupancy,
  const std::vector<std::uint8_t> & trajectory_mask)
{
  std::ofstream file(path, std::ios::binary);
  file << "P6\n" << width << " " << height << "\n255\n";
  for (int row = height - 1; row >= 0; --row) {
    for (int col = 0; col < width; ++col) {
      const auto index = static_cast<std::size_t>(col + row * width);
      const unsigned char pixel[3] = {
        trajectory_mask[index] >= 100 ? static_cast<unsigned char>(255) : static_cast<unsigned char>(occupancy[index] >= 100 ? 0 : 254),
        trajectory_mask[index] >= 100 ? static_cast<unsigned char>(64) : static_cast<unsigned char>(occupancy[index] >= 100 ? 0 : 254),
        trajectory_mask[index] >= 100 ? static_cast<unsigned char>(64) : static_cast<unsigned char>(occupancy[index] >= 100 ? 0 : 254)};
      file.write(reinterpret_cast<const char *>(pixel), 3);
    }
  }
}

static Options parse_args(int argc, char ** argv)
{
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    auto value = [&]() -> std::string { if (index + 1 >= argc) throw std::runtime_error("missing value for " + key); return argv[++index]; };
    if (key == "--pcd") options.input = value();
    else if (key == "--trajectory") options.trajectory = value();
    else if (key == "--output-dir") options.output_dir = value();
    else if (key == "--map-name") options.map_name = value();
    else if (key == "--z-min") options.z_min = std::stod(value());
    else if (key == "--z-max") options.z_max = std::stod(value());
    else if (key == "--radius") options.radius = std::stod(value());
    else if (key == "--min-neighbors") options.min_neighbors = std::stoi(value());
    else if (key == "--resolution") options.resolution = std::stod(value());
    else if (key == "--sensor-height") options.sensor_height = std::stod(value());
    else if (key == "--trajectory-search-radius") options.trajectory_search_radius = std::stod(value());
    else if (key == "--preview-max-dimension") options.preview_max_dimension = std::stoi(value());
    else if (key == "--threads") options.threads = std::stoi(value());
    else if (key == "--negative") options.negative = true;
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (options.input.empty() || options.output_dir.empty()) throw std::runtime_error("--pcd and --output-dir are required");
  return options;
}

int main(int argc, char ** argv)
{
  try {
    const Options options = parse_args(argc, argv);
#ifdef _OPENMP
    if (options.threads > 0) omp_set_num_threads(options.threads);
#endif
    const auto points = load_points(options.input);
    if (points.empty()) throw std::runtime_error("PCD is empty");
    double x_min = points[0].x, x_max = points[0].x, y_min = points[0].y, y_max = points[0].y;
    for (const auto & point : points) { x_min = std::min(x_min, point.x); x_max = std::max(x_max, point.x); y_min = std::min(y_min, point.y); y_max = std::max(y_max, point.y); }
    const int width = std::max(1, static_cast<int>(std::ceil((x_max - x_min) / options.resolution)));
    const int height = std::max(1, static_cast<int>(std::ceil((y_max - y_min) / options.resolution)));

    std::vector<Point> trajectory;
    if (!options.trajectory.empty() && fs::is_regular_file(options.trajectory)) trajectory = load_points(options.trajectory);
    double fallback_floor = 0.0;
    const auto floor_values = build_floor_values(points, trajectory, x_min, y_min, options.resolution, options.sensor_height, options.trajectory_search_radius, fallback_floor);
    std::vector<Point> filtered;
    filtered.reserve(points.size());
    for (const auto & point : points) {
      bool keep = false;
      if (floor_values.empty()) {
        keep = point.z >= options.z_min && point.z <= options.z_max;
      } else {
        const auto it = floor_values.find(xy_cell(point.x, point.y, x_min, y_min, options.resolution));
        const double floor_z = it == floor_values.end() ? fallback_floor : it->second;
        keep = point.z >= floor_z + options.z_min && point.z <= floor_z + options.z_max;
      }
      if (options.negative) keep = !keep;
      if (keep) filtered.push_back(point);
    }
    filtered = radius_filter(filtered, options.radius, options.min_neighbors);

    std::vector<std::uint8_t> occupancy(static_cast<std::size_t>(width) * height, 0);
    for (const auto & point : filtered) {
      const int col = static_cast<int>(std::floor((point.x - x_min) / options.resolution));
      const int row = static_cast<int>(std::floor((point.y - y_min) / options.resolution));
      if (col >= 0 && col < width && row >= 0 && row < height) occupancy[col + row * width] = 100;
    }
    fs::create_directories(options.output_dir);
    const fs::path pgm = options.output_dir / (options.map_name + ".pgm");
    const fs::path yaml = options.output_dir / (options.map_name + ".yaml");
    const fs::path preview = options.output_dir / (options.map_name + ".preview.pgm");
    const fs::path trajectory_overlay = options.output_dir / (options.map_name + "_with_trajectory.ppm");
    write_pgm(pgm, width, height, occupancy);
    std::ofstream yaml_file(yaml);
    yaml_file << "image: " << pgm.filename().string() << "\nmode: trinary\nresolution: " << options.resolution << "\norigin: [" << x_min << ", " << y_min << ", 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n";
    if (!trajectory.empty()) {
      std::vector<std::uint8_t> trajectory_mask(static_cast<std::size_t>(width) * height, 0);
      for (const auto & point : trajectory) {
        const int col = static_cast<int>(std::floor((point.x - x_min) / options.resolution));
        const int row = static_cast<int>(std::floor((point.y - y_min) / options.resolution));
        if (col >= 0 && col < width && row >= 0 && row < height) trajectory_mask[col + row * width] = 100;
      }
      write_trajectory_overlay_ppm(trajectory_overlay, width, height, occupancy, trajectory_mask);
    }
    const int scale = 1;
    const int preview_width = (width + scale - 1) / scale;
    const int preview_height = (height + scale - 1) / scale;
    std::vector<std::uint8_t> preview_occupancy(static_cast<std::size_t>(preview_width) * preview_height, 0);
    for (int row = 0; row < preview_height; ++row) for (int col = 0; col < preview_width; ++col) preview_occupancy[col + row * preview_width] = occupancy[std::min(height - 1, row * scale) * width + std::min(width - 1, col * scale)];
    write_pgm(preview, preview_width, preview_height, preview_occupancy);
    const fs::path summary = options.output_dir / (options.map_name + ".summary.txt");
    std::ofstream summary_file(summary);
    summary_file << "width=" << width << "\nheight=" << height << "\npreview_width=" << preview_width << "\npreview_height=" << preview_height << "\nraw_count=" << points.size() << "\nfiltered_count=" << filtered.size() << "\nx_min=" << x_min << "\ny_min=" << y_min << "\npgm=" << pgm.string() << "\nyaml=" << yaml.string() << "\npreview_pgm=" << preview.string() << "\n";
    if (!trajectory.empty()) summary_file << "trajectory_overlay_ppm=" << trajectory_overlay.string() << "\n";
    std::cout << "ok\n";
    return 0;
  } catch (const std::exception & error) {
    std::cerr << error.what() << "\n";
    return 1;
  }
}
