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
| [sparql/eval](sparql/eval/manifest.ttl) | query evaluation: sequence patterns, ordering, CONSTRUCT, gap patterns, UNNEST, sequence functions, and [array-syntax.md](https://github.com/rdf-array/rdf-array/blob/rdf-sequences/docs/array-syntax.md) §4.1's twelve queries over its nested data (`data-nested.ttl`) with their results |
| [sparql/update](sparql/update/manifest.ttl) | update evaluation: INSERT DATA, DELETE DATA, spreading a sequence with UNNEST |
| [sparql/syntax-query](sparql/syntax-query/manifest.ttl) | positive syntax (every evaluation query, and the lexing and expression forms of array-syntax.md §5) and negative syntax (`[2:4]`, `[...]`, a gap in a CONSTRUCT template, `UNNEST` without `AS`, the former `((e))[i]`) |
| [sparql/results](sparql/results/manifest.ttl) | one result set with sequences in SPARQL JSON, XML, CSV and TSV |

`mf:requires` says what a test needs, in the [rdf-array test vocabulary](https://rdf-array.github.io/rdf-array/vocab/):
`ra:Sequences`, `ra:SequencePatterns`, `ra:SequenceResults`, and, for the array syntax of
[array-syntax.md](https://github.com/rdf-array/rdf-array/blob/rdf-sequences/docs/array-syntax.md) §1, `ra:GapPatterns`
(`...` and `...?rest` in a sequence pattern), `ra:Unnest` (`UNNEST(expr AS ?x AT ?i)`) and `ra:SequenceFunctions`
(`isSEQ`, `SEQLEN`, `SEQ`, `expr[i]`, `expr[m...n]`, `?x IN ?seq`). That syntax replaced the `((element))[index]`
position patterns (`ra:PositionPatterns`) on 2026-10-31: `((?e))[?i]` and `((?e))[*]` became `UNNEST` on the
sequence bound by the triple pattern, `((?e))[n]` a pattern with a gap after `?e`, and `((?e))[?i]` with `?i`
bound earlier the index `?seq[?i]`; every rewritten test keeps its expected result.

## Slots (branch `rdf-undef`)

On this branch every manifest also carries the empty slot of a sequence, `( 1 undef 3 )`
([rdf-undef.md](https://github.com/rdf-array/rdf-array/blob/rdf-undef/docs/rdf-undef.md)): the tests are named `undef-*`
and require `ra:UndefSlots`. Syntax: positive and negative in Turtle, TriG, N-Triples, N-Quads and SPARQL. Evaluation:
§3's table row by row over `data-undef.ttl`, seeded from jena-array's `TestUndefSlots`. Results: `undef-values.srj` and
`.srx`. `python3 bin/build.py --jena-only` leaves out the cross-check of these tests against N3.js-array and
comunica-array; the plain build needs those two on their `rdf-undef` branches.

## How the expectations were made

[bin/build.py](bin/build.py) holds every case and writes every file; nothing here is edited by hand.
Each RDF syntax test's input is read by jena-array and by N3.js-array, and the two readings must be
isomorphic, blank nodes inside sequences included; a negative test must be rejected by both. Each SPARQL
test is evaluated by jena-array, whose result is the expectation, and comunica-array must give the same
result for every test whose features it has; the gap-pattern, UNNEST and function tests have only jena-array
so far. The build needs the implementations checked out beside this repository (see the script's header).

**Until jena-array reads the array syntax**, which no implementation did when it was adopted, the SPARQL files
that use it were produced from `build.py`'s tables by rdf-array's array-syntax harness
(`tools/array-syntax`: SPARQL.js 3.7.4's grammar with the §1.1 productions, and the evaluator of `demo.js`):
every query and update parses or is rejected as its manifest says, the rewritten tests reproduce their
previous results, and §4.1's results equal the tables in the note. `python3 bin/build.py --check` must
wait for jena-array and should then reproduce these files.

The tests were seeded from the implementations' own tests, which stay where they are;
[contrib-duplicates.md](https://github.com/rdf-array/rdf-array/blob/rdf-sequences/management/contrib-duplicates.md) in
rdf-array/rdf-array lists which test each one reproduces (the rewritten position tests still name the
implementations' position-pattern tests they came from).
