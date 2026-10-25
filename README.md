# rdf-tests-contrib

Tests that every [rdf-array](https://github.com/rdf-array/rdf-array) implementation of Turtle, TriG,
N-Triples, N-Quads and SPARQL can share, but that no W3C suite contains because they test what rdf-array
adds: the sequence term `( e1 e2 … )`. It is laid out like [rdf-tests-array](https://github.com/rdf-array/rdf-tests-array),
the rdf-array fork of the W3C suites, in the same manifest vocabulary, so a runner that walks one walks the
other. Published at <https://rdf-array.github.io/rdf-tests-contrib/>.

| Directory | Tests |
|---|---|
| [rdf/rdf-turtle](rdf/rdf-turtle/manifest.ttl), [rdf-trig](rdf/rdf-trig/manifest.ttl) | evaluation tests (input → N-Triples-array / N-Quads-array) and negative syntax tests |
| [rdf/rdf-n-triples](rdf/rdf-n-triples/manifest.ttl), [rdf-n-quads](rdf/rdf-n-quads/manifest.ttl) | N-Triples-array and N-Quads-array positive and negative syntax tests |
| [sparql/eval](sparql/eval/manifest.ttl) | query evaluation: sequence patterns, ordering, CONSTRUCT, position patterns, sequence functions |
| [sparql/update](sparql/update/manifest.ttl) | update evaluation: INSERT DATA, DELETE DATA, spreading a sequence |
| [sparql/syntax-query](sparql/syntax-query/manifest.ttl) | positive syntax (every evaluation query) and negative syntax |
| [sparql/results](sparql/results/manifest.ttl) | one result set with sequences in SPARQL JSON, XML, CSV and TSV |

`mf:requires` says what a test needs, in the [rdf-array test vocabulary](https://rdf-array.github.io/rdf-array/vocab/):
`ra:Sequences`, `ra:SequencePatterns`, `ra:SequenceResults`, and, for the syntax proposed today and expected to
change with ongoing research, `ra:PositionPatterns` (`((element))[index]`) and `ra:SequenceFunctions`
(`isSEQ`, `SEQLEN`, `SEQ`, `expr[i]`).

## How the expectations were made

[bin/build.py](bin/build.py) holds every case and writes every file; nothing here is edited by hand.
Each RDF syntax test's input is read by jena-array and by N3.js-array, and the two readings must be
isomorphic, blank nodes inside sequences included; a negative test must be rejected by both. Each SPARQL
test is evaluated by jena-array, whose result is the expectation, and comunica-array must give the same
result for every test whose features it has; the position-pattern and function tests have only jena-array
so far. `python3 bin/build.py --check` rebuilds and fails if anything would change. The build needs the
implementations checked out beside this repository (see the script's header).

The tests were seeded from the implementations' own tests, which stay where they are;
[contrib-duplicates.md](https://github.com/rdf-array/rdf-array/blob/main/contrib-duplicates.md) in
rdf-array/rdf-array lists which test each one reproduces.
