#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#include <cmath>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdexcept>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs = std::filesystem;
struct Point { float x, y, z; };
struct Cell { int x, y; bool operator==(const Cell &o) const { return x == o.x && y == o.y; } };
struct Hash { std::size_t operator()(const Cell &c) const { return (static_cast<std::size_t>(static_cast<std::uint32_t>(c.x)) << 32) ^ static_cast<std::uint32_t>(c.y); } };
struct Header {
  std::vector<std::string> fields;
  std::vector<int> sizes, counts;
  std::vector<char> types;
  std::size_t points = 0, offset = 0;
  std::string data;
};
struct ChunkRange { int id, x, y; std::size_t begin, end; fs::path path; };
using CellCounts = std::vector<std::pair<Cell, std::size_t>>;

static std::vector<std::uint8_t> read_file(const fs::path &p) {
  std::ifstream f(p, std::ios::binary);
  if (!f) throw std::runtime_error("cannot open PCD: " + p.string());
  f.seekg(0, std::ios::end);
  auto n = static_cast<std::size_t>(f.tellg());
  f.seekg(0);
  std::vector<std::uint8_t> b(n);
  f.read(reinterpret_cast<char *>(b.data()), static_cast<std::streamsize>(n));
  return b;
}

static Header parse_header(const std::vector<std::uint8_t> &b) {
  Header h;
  std::size_t p = 0;
  while (p < b.size()) {
    auto e = std::find(b.begin() + static_cast<std::ptrdiff_t>(p), b.end(), '\n');
    std::string line(reinterpret_cast<const char *>(b.data() + p), static_cast<std::size_t>(e - (b.begin() + static_cast<std::ptrdiff_t>(p))));
    p = e == b.end() ? b.size() : static_cast<std::size_t>(e - b.begin()) + 1;
    std::istringstream s(line);
    std::string key; s >> key;
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (key == "fields") for (std::string v; s >> v;) h.fields.push_back(v);
    else if (key == "size") for (int v; s >> v;) h.sizes.push_back(v);
    else if (key == "type") for (char v; s >> v;) h.types.push_back(v);
    else if (key == "count") for (int v; s >> v;) h.counts.push_back(v);
    else if (key == "points") s >> h.points;
    else if (key == "width" && h.points == 0) s >> h.points;
    else if (key == "data") { s >> h.data; h.offset = p; break; }
  }
  if (h.fields.empty() || h.fields.size() != h.sizes.size() || h.fields.size() != h.types.size()) throw std::runtime_error("invalid PCD header");
  if (h.counts.empty()) h.counts.assign(h.fields.size(), 1);
  return h;
}

static Header parse_header_stream(std::ifstream &f) {
  Header h;
  std::string line;
  while (std::getline(f, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::istringstream s(line);
    std::string key; s >> key;
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (key == "fields") for (std::string v; s >> v;) h.fields.push_back(v);
    else if (key == "size") for (int v; s >> v;) h.sizes.push_back(v);
    else if (key == "type") for (char v; s >> v;) h.types.push_back(v);
    else if (key == "count") for (int v; s >> v;) h.counts.push_back(v);
    else if (key == "points") s >> h.points;
    else if (key == "width" && h.points == 0) s >> h.points;
    else if (key == "data") { s >> h.data; break; }
  }
  if (h.fields.empty() || h.fields.size() != h.sizes.size() || h.fields.size() != h.types.size()) throw std::runtime_error("invalid PCD header");
  if (h.counts.empty()) h.counts.assign(h.fields.size(), 1);
  return h;
}

static int field(const Header &h, const std::string &name) {
  auto it = std::find(h.fields.begin(), h.fields.end(), name);
  if (it == h.fields.end()) throw std::runtime_error("PCD is missing field " + name);
  return static_cast<int>(it - h.fields.begin());
}

static std::size_t offset(const Header &h, int target) {
  std::size_t n = 0;
  for (int i = 0; i < target; ++i) n += static_cast<std::size_t>(h.sizes[i] * h.counts[i]);
  return n;
}

static std::uint32_t u32(const std::uint8_t *p) {
  return p[0] | (static_cast<std::uint32_t>(p[1]) << 8) | (static_cast<std::uint32_t>(p[2]) << 16) | (static_cast<std::uint32_t>(p[3]) << 24);
}

static std::vector<std::uint8_t> lzf(const std::uint8_t *p, std::size_t n, std::size_t expected) {
  std::vector<std::uint8_t> out(expected);
  std::size_t i = 0;
  std::size_t o = 0;
  while (i < n) {
    auto c = p[i++];
    if (c < 32) {
      auto len = static_cast<std::size_t>(c) + 1;
      if (i + len > n) throw std::runtime_error("truncated LZF literal");
      if (o + len > expected) throw std::runtime_error("LZF literal exceeds output size");
      std::memcpy(out.data() + o, p + i, len);
      i += len;
      o += len;
      continue;
    }
    std::size_t len = c >> 5, ref = static_cast<std::size_t>(c & 31) << 8;
    if (len == 7) { if (i >= n) throw std::runtime_error("truncated LZF length"); len += p[i++]; }
    if (i >= n) throw std::runtime_error("truncated LZF reference");
    ref += p[i++]; len += 2;
    if (ref + 1 > o) throw std::runtime_error("invalid LZF reference");
    if (o + len > expected) throw std::runtime_error("LZF reference exceeds output size");
    auto pos = o - ref - 1;
    for (std::size_t j = 0; j < len; ++j) out[o++] = out[pos++];
  }
  if (o != expected) throw std::runtime_error("LZF output size mismatch");
  return out;
}

static void lzf_into(
    const std::uint8_t *p,
    std::size_t n,
    std::uint8_t *out,
    std::size_t expected
) {
  std::size_t i = 0;
  std::size_t o = 0;
  while (i < n) {
    const auto c = p[i++];
    if (c < 32) {
      const auto len = static_cast<std::size_t>(c) + 1;
      if (i + len > n) throw std::runtime_error("truncated LZF literal");
      if (o + len > expected) throw std::runtime_error("LZF literal exceeds output size");
      std::memcpy(out + o, p + i, len);
      i += len;
      o += len;
      continue;
    }
    std::size_t len = c >> 5;
    std::size_t ref = static_cast<std::size_t>(c & 31) << 8;
    if (len == 7) {
      if (i >= n) throw std::runtime_error("truncated LZF length");
      len += p[i++];
    }
    if (i >= n) throw std::runtime_error("truncated LZF reference");
    ref += p[i++];
    len += 2;
    if (ref + 1 > o) throw std::runtime_error("invalid LZF reference");
    if (o + len > expected) throw std::runtime_error("LZF reference exceeds output size");
    auto pos = o - ref - 1;
    for (std::size_t j = 0; j < len; ++j) out[o++] = out[pos++];
  }
  if (o != expected) throw std::runtime_error("LZF output size mismatch");
}

static float scalar(const std::uint8_t *p, int size, char type) {
  if (type == 'F' && size == 4) { float v; std::memcpy(&v, p, 4); return v; }
  if (type == 'F' && size == 8) { double v; std::memcpy(&v, p, 8); return static_cast<float>(v); }
  throw std::runtime_error("unsupported PCD scalar type");
}

static CellCounts summarize_binary_compressed(
    const fs::path &path,
    double chunk_size,
    std::size_t &total_points
) {
  std::ifstream file(path, std::ios::binary);
  if (!file) throw std::runtime_error("cannot open PCD: " + path.string());
  auto h = parse_header_stream(file);
  if (h.data != "binary_compressed") {
    throw std::runtime_error("summary fast path requires DATA binary_compressed");
  }
  const int xi = field(h, "x");
  const int yi = field(h, "y");
  const auto compressed_offset = static_cast<std::size_t>(file.tellg());
  std::uint8_t sizes[8];
  file.read(reinterpret_cast<char *>(sizes), 8);
  if (file.gcount() != 8) throw std::runtime_error("truncated compressed PCD");
  const auto compressed_size = u32(sizes);
  const auto uncompressed_size = u32(sizes + 4);
  const int input_fd = ::open(path.c_str(), O_RDONLY);
  if (input_fd < 0) throw std::runtime_error("cannot map compressed PCD payload");
  const auto input_map_size = compressed_offset + 8 + compressed_size;
  auto *input_map = static_cast<std::uint8_t *>(
      ::mmap(nullptr, input_map_size, PROT_READ, MAP_PRIVATE, input_fd, 0));
  ::close(input_fd);
  if (input_map == MAP_FAILED) throw std::runtime_error("cannot map compressed PCD payload");

  char output_template[] = "/tmp/pcd-chunker-lzf-XXXXXX";
  const int output_fd = ::mkstemp(output_template);
  if (output_fd < 0) {
    ::munmap(input_map, input_map_size);
    throw std::runtime_error("cannot create temporary decompression file");
  }
  ::unlink(output_template);
  if (::ftruncate(output_fd, static_cast<off_t>(uncompressed_size)) != 0) {
    ::close(output_fd);
    ::munmap(input_map, input_map_size);
    throw std::runtime_error("cannot size temporary decompression file");
  }
  auto *data = static_cast<std::uint8_t *>(
      ::mmap(nullptr, uncompressed_size, PROT_READ | PROT_WRITE, MAP_SHARED, output_fd, 0));
  ::close(output_fd);
  if (data == MAP_FAILED) {
    ::munmap(input_map, input_map_size);
    throw std::runtime_error("cannot map temporary decompression file");
  }
  lzf_into(input_map + compressed_offset + 8, compressed_size, data, uncompressed_size);
  ::munmap(input_map, input_map_size);
  ::msync(data, uncompressed_size, MS_ASYNC);
  ::madvise(data, uncompressed_size, MADV_SEQUENTIAL);

  const auto xo = offset(h, xi) * h.points;
  const auto yo = offset(h, yi) * h.points;
  const auto thread_count =
#ifdef _OPENMP
      std::max(1, omp_get_max_threads());
#else
      1;
#endif
  std::vector<std::unordered_map<Cell, std::size_t, Hash>> local_counts(
      static_cast<std::size_t>(thread_count)
  );

  constexpr std::size_t block_points = 1U << 20;
  const auto block_count = (h.points + block_points - 1) / block_points;
#pragma omp parallel for schedule(static)
  for (std::int64_t block = 0; block < static_cast<std::int64_t>(block_count); ++block) {
#ifdef _OPENMP
    const auto thread_id = omp_get_thread_num();
#else
    const auto thread_id = 0;
#endif
    const auto begin = static_cast<std::size_t>(block) * block_points;
    const auto end = std::min(h.points, begin + block_points);
    for (auto index = begin; index < end; ++index) {
      const float x = scalar(
          data + xo + index * h.sizes[xi], h.sizes[xi], h.types[xi]);
      const float y = scalar(
          data + yo + index * h.sizes[yi], h.sizes[yi], h.types[yi]);
      const Cell cell{
          static_cast<int>(std::floor(x / chunk_size + 0.5)),
          static_cast<int>(std::floor(y / chunk_size + 0.5)),
      };
      ++local_counts[static_cast<std::size_t>(thread_id)][cell];
    }
    const auto page_size = static_cast<std::size_t>(::sysconf(_SC_PAGESIZE));
    const auto release = [&](std::size_t start, std::size_t length) {
      const auto aligned_start = start / page_size * page_size;
      const auto aligned_end = (start + length + page_size - 1) / page_size * page_size;
      if (aligned_end > aligned_start) {
        ::madvise(data + aligned_start, aligned_end - aligned_start, MADV_DONTNEED);
      }
    };
    release(xo + begin * h.sizes[xi], (end - begin) * h.sizes[xi]);
    release(yo + begin * h.sizes[yi], (end - begin) * h.sizes[yi]);
  }
  ::munmap(data, uncompressed_size);

  std::map<Cell, std::size_t, bool (*)(const Cell &, const Cell &)> ordered(
      [](const Cell &a, const Cell &b) {
        return a.x < b.x || (a.x == b.x && a.y < b.y);
      });
  for (const auto &counts : local_counts) {
    for (const auto &[cell, count] : counts) ordered[cell] += count;
  }
  total_points = h.points;
  CellCounts result;
  result.reserve(ordered.size());
  for (const auto &[cell, count] : ordered) result.emplace_back(cell, count);
  return result;
}

static bool is_binary_compressed(const fs::path &path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) throw std::runtime_error("cannot open PCD: " + path.string());
  return parse_header_stream(file).data == "binary_compressed";
}

static std::vector<Point> load(const fs::path &path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) throw std::runtime_error("cannot open PCD: " + path.string());
  auto h = parse_header_stream(file);
  int xi = field(h, "x"), yi = field(h, "y"), zi = field(h, "z");
  std::vector<Point> out(h.points);
  if (h.data == "ascii") {
    for (std::size_t i = 0; i < h.points; ++i) { std::vector<float> v(h.fields.size()); for (auto &x : v) file >> x; out[i] = {v[xi], v[yi], v[zi]}; }
    return out;
  }
  std::vector<std::uint8_t> data;
  if (h.data == "binary_compressed") {
    std::uint8_t sizes[8];
    file.read(reinterpret_cast<char *>(sizes), 8);
    if (file.gcount() != 8) throw std::runtime_error("truncated compressed PCD");
    const auto compressed_size = u32(sizes);
    const auto uncompressed_size = u32(sizes + 4);
    std::vector<std::uint8_t> compressed(compressed_size);
    file.read(reinterpret_cast<char *>(compressed.data()), static_cast<std::streamsize>(compressed.size()));
    if (static_cast<std::size_t>(file.gcount()) != compressed.size()) throw std::runtime_error("truncated compressed PCD payload");
    data = lzf(compressed.data(), compressed.size(), uncompressed_size);
    compressed.clear();
    compressed.shrink_to_fit();
    const auto xo = offset(h, xi) * h.points, yo = offset(h, yi) * h.points, zo = offset(h, zi) * h.points;
#pragma omp parallel for schedule(static)
    for (std::int64_t i = 0; i < static_cast<std::int64_t>(h.points); ++i) out[static_cast<std::size_t>(i)] = {scalar(data.data() + xo + static_cast<std::size_t>(i) * h.sizes[xi], h.sizes[xi], h.types[xi]), scalar(data.data() + yo + static_cast<std::size_t>(i) * h.sizes[yi], h.sizes[yi], h.types[yi]), scalar(data.data() + zo + static_cast<std::size_t>(i) * h.sizes[zi], h.sizes[zi], h.types[zi])};
    return out;
  }
  if (h.data == "binary") {
    std::size_t step = 0; for (std::size_t i = 0; i < h.fields.size(); ++i) step += h.sizes[i] * h.counts[i];
    std::vector<std::uint8_t> bytes(step * h.points);
    file.read(reinterpret_cast<char *>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    if (static_cast<std::size_t>(file.gcount()) != bytes.size()) throw std::runtime_error("truncated binary PCD payload");
    const auto xo = offset(h, xi), yo = offset(h, yi), zo = offset(h, zi);
#pragma omp parallel for schedule(static)
    for (std::int64_t i = 0; i < static_cast<std::int64_t>(h.points); ++i) { auto *p = bytes.data() + h.offset + static_cast<std::size_t>(i) * step; out[static_cast<std::size_t>(i)] = {scalar(p + xo, h.sizes[xi], h.types[xi]), scalar(p + yo, h.sizes[yi], h.types[yi]), scalar(p + zo, h.sizes[zi], h.types[zi])}; }
    return out;
  }
  throw std::runtime_error("unsupported PCD DATA type: " + h.data);
}

static void save(const fs::path &path, const std::vector<Point> &points) {
  std::ofstream f(path, std::ios::binary);
  f << "# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH " << points.size() << "\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS " << points.size() << "\nDATA binary\n";
  f.write(reinterpret_cast<const char *>(points.data()), static_cast<std::streamsize>(points.size() * sizeof(Point)));
}

static int main_run(int argc, char **argv) {
  fs::path input, output; double size = 100, sx = 0, sy = 0, sz = 0, voxel = 0; bool force = false; bool summary_only = false; int workers = 1;
  for (int i = 1; i < argc; ++i) { std::string k = argv[i]; auto val = [&]() { if (++i >= argc) throw std::runtime_error("missing value for " + k); return std::string(argv[i]); }; if (k == "--input") input = val(); else if (k == "--output") output = val(); else if (k == "--chunk-size") size = std::stod(val()); else if (k == "--start-x") sx = std::stod(val()); else if (k == "--start-y") sy = std::stod(val()); else if (k == "--start-z") sz = std::stod(val()); else if (k == "--voxel-size") voxel = std::stod(val()); else if (k == "--workers") workers = std::max(1, std::stoi(val())); else if (k == "--force") force = true; else if (k == "--summary-only") summary_only = true; else if (k == "--cache-mb") { (void)val(); } }
#ifdef _OPENMP
  omp_set_num_threads(workers);
#endif
  if (input.empty() || output.empty() || size <= 0) throw std::runtime_error("--input, --output and positive --chunk-size are required");
  if (fs::exists(output) && !force) throw std::runtime_error("output_dir already exists: " + output.string() + ". Use force to overwrite it.");
  fs::create_directories(output);
  if (force) {
    std::error_code ec;
    fs::remove(output / "index.txt", ec);
    for (const auto &entry : fs::directory_iterator(output)) {
      if (entry.path().extension() == ".pcd" && entry.path().stem().string().find_first_not_of("0123456789") == std::string::npos) fs::remove(entry.path(), ec);
    }
  }
  if (summary_only) {
    std::size_t total_input = 0;
    CellCounts counts;
    if (is_binary_compressed(input)) {
      counts = summarize_binary_compressed(input, size, total_input);
    } else {
      auto points = load(input);
      total_input = points.size();
      std::map<Cell, std::size_t, bool (*)(const Cell &, const Cell &)> ordered(
          [](const Cell &a, const Cell &b) {
            return a.x < b.x || (a.x == b.x && a.y < b.y);
          });
      for (const auto &p : points) {
        const Cell cell{
            static_cast<int>(std::floor(p.x / size + 0.5)),
            static_cast<int>(std::floor(p.y / size + 0.5)),
        };
        ++ordered[cell];
      }
      counts.reserve(ordered.size());
      for (const auto &[cell, count] : ordered) counts.emplace_back(cell, count);
    }
    std::ofstream index(output / "index.txt"); index << "0 0 0\n";
    std::size_t total = 0;
    for (std::size_t id = 0; id < counts.size(); ++id) {
      const auto &[cell, count] = counts[id];
      index << id << " " << cell.x << " " << cell.y << " " << fs::absolute(output / (std::to_string(id) + ".pcd")).string() << "\n";
      total += count;
    }
    index << "# functional points\nstart " << sx << " " << sy << " " << sz << " 0 0 0 1\n";
    std::ofstream summary(output / "chunker.summary");
    summary << "chunk_size=" << size << "\nvoxel_size=" << (voxel > 0 ? std::to_string(voxel) : "") << "\nstart_x=" << sx << "\nstart_y=" << sy << "\nstart_z=" << sz << "\ntotal_input_points=" << total_input << "\ntotal_output_points=" << total << "\nchunk_count=" << counts.size() << "\noutput_dir=" << fs::absolute(output).string() << "\nworkers=" << workers << "\nsummary_only=1\n";
    for (std::size_t id = 0; id < counts.size(); ++id) {
      const auto &[cell, count] = counts[id];
      summary << "chunk\t" << id << "\t" << cell.x << "\t" << cell.y << "\t" << count << "\t" << fs::absolute(output / (std::to_string(id) + ".pcd")).string() << "\n";
    }
    return 0;
  }
  auto points = load(input);
  std::vector<std::size_t> order(points.size());
  std::vector<Cell> cells(points.size());
#pragma omp parallel for schedule(static)
  for (std::int64_t i = 0; i < static_cast<std::int64_t>(points.size()); ++i) {
    const auto idx = static_cast<std::size_t>(i);
    order[idx] = idx;
    cells[idx] = {static_cast<int>(std::floor(points[idx].x / size + 0.5)), static_cast<int>(std::floor(points[idx].y / size + 0.5))};
  }
  std::stable_sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {
    if (cells[a].x != cells[b].x) return cells[a].x < cells[b].x;
    return cells[a].y < cells[b].y;
  });
  std::vector<ChunkRange> chunks;
  for (std::size_t begin = 0; begin < order.size();) {
    const Cell cell = cells[order[begin]];
    std::size_t end = begin + 1;
    while (end < order.size() && cells[order[end]] == cell) ++end;
    const int id = static_cast<int>(chunks.size());
    chunks.push_back({id, cell.x, cell.y, begin, end, fs::absolute(output / (std::to_string(id) + ".pcd"))});
    begin = end;
  }
  if (!summary_only) {
#pragma omp parallel for schedule(dynamic)
    for (std::int64_t ci = 0; ci < static_cast<std::int64_t>(chunks.size()); ++ci) {
      const auto &chunk = chunks[static_cast<std::size_t>(ci)];
      std::vector<Point> chunk_points;
      chunk_points.reserve(chunk.end - chunk.begin);
      for (std::size_t i = chunk.begin; i < chunk.end; ++i) chunk_points.push_back(points[order[i]]);
      save(chunk.path, chunk_points);
    }
  }
  std::ofstream index(output / "index.txt"); index << "0 0 0\n";
  std::size_t total = 0;
  for (const auto &chunk : chunks) { index << chunk.id << " " << chunk.x << " " << chunk.y << " " << chunk.path.string() << "\n"; total += chunk.end - chunk.begin; }
  index << "# functional points\nstart " << sx << " " << sy << " " << sz << " 0 0 0 1\n";
  std::ofstream summary(output / "chunker.summary");
  summary << "chunk_size=" << size << "\nvoxel_size=" << (voxel > 0 ? std::to_string(voxel) : "") << "\nstart_x=" << sx << "\nstart_y=" << sy << "\nstart_z=" << sz << "\ntotal_input_points=" << points.size() << "\ntotal_output_points=" << total << "\nchunk_count=" << chunks.size() << "\noutput_dir=" << fs::absolute(output).string() << "\nworkers=" << workers << "\nsummary_only=" << (summary_only ? 1 : 0) << "\n";
  for (const auto &chunk : chunks) summary << "chunk\t" << chunk.id << "\t" << chunk.x << "\t" << chunk.y << "\t" << (chunk.end - chunk.begin) << "\t" << chunk.path.string() << "\n";
  return 0;
}

int main(int argc, char **argv) { try { return main_run(argc, argv); } catch (const std::exception &e) { std::cerr << e.what() << "\n"; return 1; } }
