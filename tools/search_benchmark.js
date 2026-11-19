// Compare the previous scorer with prepared search metadata. This measures
// JavaScript work in Node, not rendering, GPU use or the shell's total CPU.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {performance} = require("node:perf_hooks");
const root = path.join(__dirname, "..");
const previousPath = process.argv[2];
if (!previousPath) {
  console.error("Uso: node tools/search_benchmark.js RUTA_AL_fuzzy.js_ANTERIOR");
  process.exit(1);
}
function load(file) {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(file, "utf8"), context);
  return context;
}
const previous = load(previousPath), current = load(path.join(root, "core/fuzzy.js"));
const names = ["Firefox Web Browser", "Visual Studio Code", "Calculadora", "Configuración", "Terminal", "Document Viewer", "Music Player"];
const entries = Array.from({length: 700}, (_, index) => {
  const name = current.normalize(names[index % names.length] + " " + index);
  return {name, keywords: name + " escritorio herramienta", tokens: name.split(/[^a-z0-9]+/).filter(Boolean)};
});
const queries = ["firefox", "firefx", "vis stud", "calcu", "config", "term", "document", "music", "zzzz", "editor"].map(text => ({text, words: text.split(/\s+/)}));
for (const [context, expression] of [[previous, "score(query.text, entry.name, entry.keywords)"], [current, "scoreWords(query.words, entry.name, entry.keywords, entry.tokens)"]])
  vm.runInContext(`
    const benchmarkEntries = ${JSON.stringify(entries)};
    const benchmarkQueries = ${JSON.stringify(queries)};
    function runBenchmark() {
      let checksum = 0;
      for (let repeat = 0; repeat < 4; repeat++)
        for (const query of benchmarkQueries)
          for (const entry of benchmarkEntries)
            checksum += ${expression};
      return checksum;
    }
  `, context);
function run(prepared) {
  const started = performance.now();
  const checksum = (prepared ? current : previous).runBenchmark();
  return {ms: performance.now() - started, checksum};
}
run(false); run(true);
const before = [], after = [];
for (let repeat = 0; repeat < 5; repeat++) {
  const first = run(false), second = run(true);
  if (first.checksum !== second.checksum) throw new Error("Los resultados difieren");
  before.push(first.ms); after.push(second.ms);
}
const median = values => values.slice().sort((a, b) => a - b)[Math.floor(values.length / 2)];
const beforeMs = median(before), afterMs = median(after);
console.log(JSON.stringify({type: "hyprlarp-search-benchmark", node: process.version, entries: entries.length,
  evaluations_per_sample: entries.length * queries.length * 4, samples: 5,
  before_median_ms: +beforeMs.toFixed(2), after_median_ms: +afterMs.toFixed(2),
  change_percent: +((afterMs / beforeMs - 1) * 100).toFixed(2),
  note: "Solo algoritmo de búsqueda; no representa el consumo global del escritorio"}, null, 2));
