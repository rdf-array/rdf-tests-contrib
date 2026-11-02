#!/usr/bin/env python3
"""Build rdf-tests-contrib from the case tables below, cross-checking every expectation.

    python3 bin/build.py            write rdf/ and sparql/ and their manifests
    python3 bin/build.py --check    write nothing; fail if a file would change

RDF syntax tests: each positive test's input is read by jena-array and by N3.js-array; the two readings
must be isomorphic (blank nodes inside sequences included) and the evaluation tests' expected result is
that reading. Each negative test must be rejected by both.
SPARQL tests: jena-array evaluates each query or update and its result is the expectation; comunica-array
must give the same result for every test whose features it has (sequence patterns, ordering, CONSTRUCT,
results). Gap patterns ( ... ?x ...?rest ), UNNEST(expr AS ?x AT ?i) and the functions isSEQ, SEQLEN, SEQ,
x[i], x[m...n] and ?x IN ?seq are the syntax of rdf-array's docs/array-syntax.md, which replaced the
((x))[i] position patterns on 2026-10-31; every test using them says so with mf:requires (ra:GapPatterns,
ra:Unnest, ra:SequenceFunctions), and only jena-array is expected to run them.
The rdf-undef branch adds the empty slot of a sequence (rdf-array's docs/rdf-undef.md, jena-array's TestUndefSlots):
every such test is named undef-* and requires ra:UndefSlots. `--jena-only` builds without cross-checking those
against N3.js-array and comunica-array, for use while those two do not read `undef` yet.
Implementations are found beside this checkout (../rdf-array/tools and .tools, ../N3.js-array,
../comunica-array) or through JENA_ARRAY_TOOL, N3_ARRAY and COMUNICA_ARRAY.

When the new syntax was adopted no implementation read it, so the .rq/.ru files, the .srj and .nt
expectations of the tests that use it and the syntax-query verdicts were produced from these tables by
the array-syntax harness (its patched SPARQL.js grammar and evaluator, tools/array-syntax in rdf-array);
`--check` must wait for jena-array and should then reproduce them.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT.parent / 'rdf-array' / 'tools'
sys.path.insert(0, str(TOOLS))
import rdfarray as ra  # noqa: E402
import sparql_results as sr  # noqa: E402

JT = pathlib.Path(os.environ.get('JENA_ARRAY_TOOL', ROOT.parent / 'rdf-array' / '.tools'))
JAVA = os.environ.get('JAVA', '/opt/homebrew/opt/openjdk@21/bin/java')
BASE = 'https://rdf-array.github.io/rdf-tests-contrib/'
CHECK = '--check' in sys.argv
JENA_ONLY = '--jena-only' in sys.argv
X = 'PREFIX : <http://example/>\n'
JL = 'jena-array jena-arq TestLangSequences'
JQ = 'jena-array jena-arq TestSequenceQueries'
CQ = 'comunica-array engines/query-sparql/test/QuerySparql-test.ts'
NJ = 'N3.js-array test/N3Parser-test.js'
JU = 'jena-array jena-arq TestUndefSlots'

# ---------- RDF syntaxes: name, file text, kind (eval | syntax | bad), comment, duplicates ----------
TURTLE = [
    ('seq-object', X + ':x :p (1 2) .', 'eval', 'a collection in object position is one sequence term', [f'{JL}.turtle_object_sequence_is_one_triple']),
    ('seq-empty', X + ':x :p () .', 'eval', '() is the empty sequence, not rdf:nil', [f'{JL}.empty_sequence_is_not_nil']),
    ('seq-nil-is-not-empty', 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n' + X + ':x :p rdf:nil , () .', 'eval', 'rdf:nil and () are two different terms', []),
    ('seq-nested-and-bnode-property-list', X + ':x :p ((1 2) [ :q 3 ]) .', 'eval', 'a nested sequence and a blank node property list as elements; the property list still contributes its triple', [f'{JL}.sequence_elements_nested_and_blank_node_property_list']),
    ('seq-subject', X + '(1 2) :p :o .', 'eval', 'a sequence as subject', [f'{JL}.sequence_as_subject']),
    ('seq-subject-and-object', X + '(1 2) :p (:o (3)) .', 'eval', 'sequences as subject and object of one triple', [f'{JL}.sequence_terms_pass_the_checker']),
    ('seq-mixed-elements', X + ':x :p (1 (2 3) :y "s"@en) ; :q () .\n(:a) :r :z .', 'eval', 'elements of every kind, an empty sequence, and a one-element sequence as subject', [f'{JL}.turtle_round_trip']),
    ('seq-nested-empties', X + ':x :p (() (()) ((()))) .', 'eval', 'empty sequences nested at three depths', []),
    ('seq-of-blank-nodes', X + ':x :p ([] [ :q 1 ] _:b) .\n_:b :q 2 .', 'eval', 'blank nodes, anonymous or labelled, as elements', []),
    ('seq-equal-terms', X + ':x :p (1 2) ; :q (1 2) .', 'eval', 'two equal sequences are one term', []),
    ('seq-in-bnode-property-list-subject', X + '[ :p (1) ] :q 2 .', 'eval', 'a sequence inside a blank node property list used as subject', []),
    ('seq-literal-kinds', X + 'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n:x :p (true 1.5 1e0 "x"^^xsd:string "y"@fr) .', 'eval', 'abbreviated literals as elements', []),
    ('explicit-ladder-stays-triples', 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n' + X + ':x :p _:b0 .\n_:b0 rdf:first "a" ; rdf:rest rdf:nil .', 'eval', 'rdf:first and rdf:rest written as properties are ordinary triples, not a sequence', [f'{JL}.legacy_first_rest_ladders_are_not_abbreviated']),
    ('bad-seq-predicate', X + ':s (1) :o .', 'bad', 'a sequence is not a predicate', []),
    ('bad-seq-unclosed', X + ':s :p (1 2 .', 'bad', 'an unclosed sequence', []),
    ('bad-seq-comma', X + ':s :p (1, 2) .', 'bad', 'elements are not separated by commas', []),
    ('undef-object', X + ':x :p (1 undef 3) .', 'eval', 'undef is an empty slot: the sequence has three positions and nothing at the second', [f'{JU}.turtle_slot']),
    ('undef-only', X + ':x :p (undef) ; :q (undef undef) .', 'eval', 'sequences of nothing but slots have a length', []),
    ('undef-case-insensitive', X + ':x :p (UNDEF Undef undef) .', 'eval', 'undef is case insensitive, as in SPARQL', [f'{JU}.turtle_case_insensitive_as_in_sparql']),
    ('undef-nested-subject', X + '(undef (undef 1)) :p 2 .', 'eval', 'a slot at any depth, in a sequence as subject', [f'{JU}.turtle_nested_and_subject']),
    ('undef-prefixed-name', 'PREFIX undef: <http://example/>\nundef:s undef:p (undef:o undef undef:) .', 'eval', 'undef:x is a prefixed name and undef alone a slot', [f'{JU}.turtle_prefixed_name_is_not_a_slot']),
    ('undef-adjacent', X + ':x :p (undef(undef)undef) .', 'eval', 'undef needs no white space next to a parenthesis', []),
    ('undef-with-bnodes', X + ':x :p (_:a undef [ :q (undef) ]) .', 'eval', 'slots beside blank nodes, and in a sequence inside a blank node property list', [f'{JU}.isomorphism']),
    ('undef-differs-from-shorter', X + ':x :p (1 undef) , (1) , (undef 1) , (1 2) .', 'eval', 'four different terms: a slot counts and its position matters', []),
    ('undef-equal-terms', X + ':x :p (1 undef) ; :q (1 undef) .', 'eval', 'two sequences with the same members and slots are one term', []),
    ('undef-bad-object', X + ':s :p undef .', 'bad', 'a slot is not an object', [f'{JU}.turtle_slot_only_in_a_sequence']),
    ('undef-bad-subject', X + 'undef :p 1 .', 'bad', 'a slot is not a subject', [f'{JU}.turtle_slot_only_in_a_sequence']),
    ('undef-bad-predicate', X + ':s undef :o .', 'bad', 'a slot is not a predicate', []),
    ('undef-bad-object-list', X + ':s :p (1) , undef .', 'bad', 'a slot is not an object in an object list', []),
    ('undef-bad-bnode-property-list', X + ':s :p ( [ :q undef ] ) .', 'bad', 'in a sequence, but as the object of a property list: still not a term', []),
    ('undef-bad-longer-word', X + ':s :p ( undefined ) .', 'bad', 'undefined is not undef', []),
]
TRIG = [
    ('trig-seq-in-graph', X + ':g { :x :p (1 2) }', 'eval', 'a sequence in a named graph', [f'{JL}.trig_sequence']),
    ('trig-seq-subject-in-graph', X + ':g { (:a) :p () }', 'eval', 'sequences as subject and object in a named graph', []),
    ('trig-bad-seq-graph-name', X + '(:g) { :s :p :o }', 'bad', 'a sequence is not a graph name', []),
    ('undef-trig-in-graph', X + ':g { :x :p (1 undef) . (undef) :q 2 }', 'eval', 'slots in sequences in a named graph', []),
    ('undef-trig-bad-graph-name', X + 'undef { :s :p :o }', 'bad', 'a slot is not a graph name', []),
    ('undef-trig-bad-object', X + ':g { :s :p undef }', 'bad', 'a slot is not an object', []),
]
NTRIPLES = [
    ('nt-seq-object', '<http://x> <http://p> ( "a" <http://y> ( ) ) .', 'syntax', 'N-Triples-array: a sequence of a literal, an IRI and the empty sequence', [f'{JL}.ntriples_sequence']),
    ('nt-seq-subject', '( <http://a> "b" ) <http://p> <http://o> .', 'syntax', 'N-Triples-array: a sequence as subject', []),
    ('nt-seq-nested-bnode', '<http://x> <http://p> ( _:b ( _:b ) ) .\n_:b <http://q> "c" .', 'syntax', 'N-Triples-array: a blank node inside nested sequences', []),
    ('nt-bad-seq-predicate', '<http://s> ( <http://p> ) <http://o> .', 'bad', 'a sequence is not a predicate', []),
    ('nt-bad-seq-unclosed', '<http://s> <http://p> ( "a" .', 'bad', 'an unclosed sequence', []),
    ('nt-bad-seq-prefixed-name', '<http://s> <http://p> ( ex:a ) .', 'bad', 'N-Triples has no prefixed names, inside sequences either', []),
    ('undef-nt-object', '<http://example/s> <http://example/p> ( "a" undef ( undef ) ) .', 'syntax', 'N-Triples-array: a slot as a member, at two depths', [f'{JU}.ntriples_slot']),
    ('undef-nt-subject', '( undef <http://a> ) <http://p> <http://o> .', 'syntax', 'N-Triples-array: a slot in a sequence as subject', []),
    ('undef-nt-case', '<http://s> <http://p> ( UNDEF Undef ) .', 'syntax', 'N-Triples-array: undef in any case', []),
    ('undef-nt-bad-object', '<http://example/s> <http://example/p> undef .', 'bad', 'a slot is not an object', [f'{JU}.ntriples_slot_only_in_a_sequence']),
    ('undef-nt-bad-subject', 'undef <http://p> <http://o> .', 'bad', 'a slot is not a subject', []),
    ('undef-nt-bad-predicate', '<http://s> undef <http://o> .', 'bad', 'a slot is not a predicate', []),
]
NQUADS = [
    ('nq-seq-object-in-graph', '<http://x> <http://p> ( "1" ( ) ) <http://g> .', 'syntax', 'N-Quads-array: a sequence object in a named graph', []),
    ('nq-bad-seq-graph-label', '<http://s> <http://p> <http://o> ( <http://g> ) .', 'bad', 'a sequence is not a graph label', []),
    ('undef-nq-object-in-graph', '<http://x> <http://p> ( "1" undef ) <http://g> .', 'syntax', 'N-Quads-array: a slot in a sequence in a named graph', []),
    ('undef-nq-bad-graph-label', '<http://s> <http://p> <http://o> undef .', 'bad', 'a slot is not a graph label', []),
    ('undef-nq-bad-object', '<http://s> <http://p> undef <http://g> .', 'bad', 'a slot is not an object', []),
]
SYNTAXES = [  # directory, extension, test-type prefix, cases
    ('rdf-turtle', '.ttl', 'Turtle', TURTLE), ('rdf-trig', '.trig', 'Trig', TRIG),
    ('rdf-n-triples', '.nt', 'NTriples', NTRIPLES), ('rdf-n-quads', '.nq', 'NQuads', NQUADS),
]

# ---------- SPARQL ----------
DATA = {
    'data': X.replace('PREFIX', '@prefix').rstrip('\n') + ' .\n:x :p (1 2 3) .\n:y :p (:a (:b :c)) .\n:z :p () .\n:w :p "not a sequence" .\n',
    'data-repeat': '@prefix : <http://example/> .\n:s :p (5 5) .\n:t :p (5 6) .\n',
    'data-index': '@prefix : <http://example/> .\n:s :p (10 20 30) ; :idx 2 .\n',
    'data-coding': '@prefix : <http://example/> .\n:v :coding ( [ :system :loinc ; :code "1234-5" ] ) .\n',
    # docs/array-syntax.md §4: tuples in lists, matrices (one ragged), a polyline, a flat key/value list, a tree
    'data-nested': '''@prefix : <http://example/> .
:obs1 :component ( ( "8480-6" "systolic"  ( 120 "mm[Hg]" ) )
                   ( "8462-4" "diastolic" (  80 "mm[Hg]" ) ) ) .
:obs2 :component ( ( "8480-6" "systolic"  ( 150 "mm[Hg]" ) )
                   ( "8462-4" "diastolic" (  95 "mm[Hg]" ) ) ) .
:obs3 :component ( ( "8480-6" "systolic"  ( "high" "mm[Hg]" ) ) ) .
:m1   :matrix ( ( 1 2 3 ) ( 4 5 6 ) ) .
:m2   :matrix ( ( 1 2 3 ) ( 4 5 ) ) .
:poly :points ( ( 0 0 ) ( 3 0 ) ( 3 4 ) ) .
:kv   :pairs  ( "a" 1 "b" 2 "c" 3 ) .
:tree :node   ( "root" ( ( "left" ( ) ) ( "right" ( ( "leaf" ( ) ) ) ) ) ) .
''',
}
DATA_UNDEF = '@prefix : <http://example/> .\n:x :p (1 undef 3) .\n:y :p (1 2 3) .\n:z :p (undef undef) .\n:v :w 5 .\n'
DATA.update({
    # docs/rdf-undef.md §3, and TestUndefSlots
    'data-undef': DATA_UNDEF,
    'data-undef-repeat': '@prefix : <http://example/> .\n:s1 :p (1 undef) .\n:s2 :p (undef 1) .\n:s3 :p (1 2) .\n:s4 :p (undef undef) .\n',
    'data-undef-nested': '@prefix : <http://example/> .\n:s :p ( ( undef 1 ) ) .\n',
    'data-undef-order': '@prefix : <http://example/> .\n:a :p (undef 1) .\n:b :p (undef undef) .\n:c :p (1 undef) .\n:d :p (0 1) .\n:e :p (undef) .\n:f :p (1 2) .\n',
})
# name, data, query, features, ordered?, comment, duplicates; features beyond SequencePatterns mark the array syntax
P, G, U, F = 'ra:SequencePatterns', 'ra:GapPatterns', 'ra:Unnest', 'ra:SequenceFunctions'
S = 'ra:UndefSlots'
QUERIES = [
    ('exact-sequence', 'data', 'SELECT ?s { ?s :p (1 2 3) }', [P], False, 'a sequence term in a pattern matches an equal sequence', [f'{JQ}.exact_sequence_pattern']),
    ('sequence-variables', 'data', 'SELECT ?a ?b { :x :p (1 ?a ?b) }', [P], False, 'variables inside a sequence bind to its elements', [f'{JQ}.sequence_pattern_with_variables']),
    ('sequence-length-mismatch', 'data', 'SELECT ?a { :x :p (1 ?a) }', [P], False, 'a pattern of another length does not match', [f'{JQ}.sequence_pattern_length_must_match']),
    ('sequence-repeated-variable-length', 'data', 'SELECT ?a { :x :p (?a ?a ?a) }', [P], False, 'a repeated variable must match equal elements', [f'{JQ}.sequence_pattern_length_must_match']),
    ('sequence-repeated-variable', 'data-repeat', 'SELECT ?s { ?s :p (?v ?v) }', [P], False, 'a repeated variable binds once', [f'{JQ}.repeated_variable_in_pattern']),
    ('sequence-nested', 'data', 'SELECT ?s ?c { ?s :p (:a (?b ?c)) }', [P], False, 'variables inside a nested sequence', [f'{JQ}.nested_sequence_pattern']),
    ('sequence-empty', 'data', 'SELECT ?s { ?s :p () }', [P], False, '() matches the empty sequence', [f'{JQ}.empty_sequence_pattern']),
    ('sequence-whole-binding', 'data', 'SELECT ?s ?seq { ?s :p ?seq } ORDER BY ?s', [P], True, 'a variable binds a whole sequence; the results carry sequence terms', [f'{JQ}.json_results_carry_sequences']),
    ('sequence-order-by', 'data', 'SELECT ?s ?o { ?s :p ?o } ORDER BY ?o', [P], True, 'sequences order after literals, element by element, the empty sequence first', [f'{JQ}.sequences_in_order_by_and_equality']),
    ('sequence-join-equality', 'data', 'SELECT ?s { ?s :p ?seq . :x :p ?seq }', [P], False, 'equal sequences join', [f'{JQ}.sequences_in_order_by_and_equality']),
    ('sequence-bnode-property-list', 'data-coding', 'SELECT ?code { ?v :coding ( [ :code ?code ] ) }', [P], False, 'a blank node property list inside a sequence pattern', [f'{CQ} "should handle a sequence holding a blank node property list"']),
    ('construct-sequence', 'data', 'CONSTRUCT { ?s :r (?a ?b) } WHERE { ?s :p (?a ?b ?c) }', [P], False, 'CONSTRUCT builds a sequence from bound elements', [f'{JQ}.construct_sequence_from_pattern']),
    ('position-constant', 'data', 'SELECT ?e { :x :p ( ?first ?e ... ) }', [P, G], False, '( ?first ?e ... ): the second member, by a gap after it', [f'{JQ}.position_constant']),
    ('position-out-of-range', 'data', 'SELECT ?e { :x :p ( ?a ?b ?c ?e ... ) }', [P, G], False, 'a pattern reaching past the end matches nothing', [f'{JQ}.position_constant']),
    ('position-variable', 'data', 'SELECT ?i ?e { :x :p ?seq UNNEST(?seq AS ?e AT ?i) } ORDER BY ?i', [P, U], True, 'UNNEST(?seq AS ?e AT ?i): every member, with its 1-based position', [f'{JQ}.position_variable']),
    ('position-any', 'data', 'SELECT ?s ?e { ?s :p ?seq UNNEST(?seq AS ?e) } ORDER BY ?s ?e', [P, U], True, 'UNNEST without AT: every member of every sequence; a non-sequence yields nothing', [f'{JQ}.position_any']),
    ('position-constant-element', 'data', 'SELECT ?s { ?s :p ( :a ... ) }', [P, G], False, 'a constant first member, then a gap', [f'{JQ}.position_constant_element_pattern']),
    ('position-constant-element-elsewhere', 'data', 'SELECT ?s { ?s :p ( ?first :a ... ) }', [P, G], False, 'the constant is not at that position', [f'{JQ}.position_constant_element_pattern']),
    ('position-nested', 'data', 'SELECT ?e { :y :p ( ?first ( ?e ... ) ... ) }', [P, G], False, 'the first member of the second member', [f'{JQ}.nested_position_patterns']),
    ('position-bound-earlier', 'data-index', 'SELECT ?e { :s :idx ?i . :s :p ?seq BIND(?seq[?i] AS ?e) }', [P, F], False, 'a position bound by an earlier pattern indexes the sequence', [f'{JQ}.position_bound_by_earlier_pattern']),
    ('function-seqlen-isseq-index', 'data', 'SELECT ?s ?n ?second ?isseq { ?s :p ?seq . FILTER(isSEQ(?seq)) BIND(SEQLEN(?seq) AS ?n) BIND(?seq[2] AS ?second) BIND(isSEQ(?seq) AS ?isseq) } ORDER BY ?n', [P, F], True, 'SEQLEN, isSEQ and x[i]; an index out of range leaves the variable unbound', [f'{JQ}.functions_seqlen_isseq_index']),
    ('function-isseq-false', 'data', 'SELECT ?s { ?s :p ?o FILTER(!isSEQ(?o)) }', [P, F], False, 'isSEQ is false for other terms', [f'{JQ}.isseq_false_for_other_terms']),
    ('function-chained-index', 'data', 'SELECT ?e { :y :p ?seq BIND(?seq[2][1] AS ?e) }', [P, F], False, 'x[i][j] indexes nested sequences', [f'{JQ}.chained_index_in_expression']),
    ('function-seq-constructor', '-', 'SELECT ?seq { BIND(SEQ(1, :a, SEQ()) AS ?seq) }', [P, F], False, 'SEQ(...) makes a sequence', [f'{JQ}.seq_constructor']),
    ('function-seq-equality', 'data', 'SELECT ?s { ?s :p ?seq FILTER(?seq = SEQ(1, 2, 3)) }', [P, F], False, '= compares whole sequences', [f'{JQ}.sequences_in_order_by_and_equality']),
    # docs/array-syntax.md §4.1, with its results
    ('gap-tuple-anywhere', 'data-nested', 'SELECT ?obs ?v ?unit WHERE {\n  ?obs :component ( ... ( "8480-6" ?name ( ?v ?unit ) ) ... )\n}', [P, G], False, 'a 3-tuple anywhere in a list of tuples: gaps before and after a nested pattern', []),
    ('gap-first-last', 'data-nested', 'SELECT ?x0 ?last WHERE { :poly :points ( ( ?x0 ?y0 ) ... ?last ) }', [P, G], False, 'the first member, nested into, and the last member', []),
    ('gap-named-head-tail', 'data-nested', 'SELECT ?h ?t ?t2 WHERE {\n  :poly :points ( ?h ...?t ) .\n  :poly :points ?pts BIND(?pts[2...] AS ?t2)\n}', [P, G, F], False, 'a named gap ...?t binds the rest of the list, as the slice [2...] does', []),
    ('gap-named-position', 'data-nested', 'SELECT ?x ?i WHERE { :poly :points ( ...?pre ?x ... ) BIND(SEQLEN(?pre) + 1 AS ?i) }', [P, G, F], False, 'the named gap before a member holds the members before it: SEQLEN(?pre) + 1 is its position', []),
    ('gap-nested-tree', 'data-nested', 'SELECT ?child ?grandchild WHERE {\n  :tree :node ( "root" ( ... ( ?child ( ... ( ?grandchild ?kids ) ... ) ) ... ) )\n}', [P, G], False, 'gaps at two levels of recursive data', []),
    ('unnest-matrix-cells', 'data-nested', 'SELECT ?m ?i ?j ?x WHERE {\n  ?m :matrix ?rows .\n  UNNEST(?rows AS ?row AT ?i)\n  UNNEST(?row AS ?x AT ?j)\n}', [P, U], False, 'UNNEST twice: every cell with its row and column', []),
    ('unnest-index-filter', 'data-nested', 'SELECT ?obs ?i ?code ?v WHERE {\n  ?obs :component ?c .\n  UNNEST(?c AS ?comp AT ?i)\n  BIND(?comp[1] AS ?code)\n  BIND(?comp[3][1] AS ?v)\n  FILTER(?v >= 90)\n}', [P, U, F], False, "UNNEST, then ?comp[1] and ?comp[3][1] into each tuple; comparing the string 'high' with 90 is a type error, so :obs3 drops out", []),
    ('unnest-slice-rows', 'data-nested', 'SELECT ?m ?i ?cols WHERE {\n  ?m :matrix ?rows .\n  UNNEST(?rows AS ?row AT ?i)\n  BIND(?row[2...3] AS ?cols)\n}', [P, U, F], False, 'a slice of every row, clamped to the short row', []),
    ('unnest-stride', 'data-nested', 'SELECT ?k ?v WHERE {\n  :kv :pairs ?p .\n  UNNEST(?p AS ?k AT ?i)\n  BIND(?p[?i + 1] AS ?v)\n  FILTER(?i - 2 * FLOOR(?i / 2) = 1)\n}', [P, U, F], False, 'the odd positions of a flat key/value list, each with the member after it: ?p[?i + 1]', []),
    ('function-chained-index-seqlen', 'data-nested', 'SELECT ?m ?cell ?len WHERE {\n  ?m :matrix ?rows .\n  BIND(?rows[2][3] AS ?cell)\n  BIND(SEQLEN(?rows[2]) AS ?len)\n}', [P, F], False, '?rows[2][3] and SEQLEN(?rows[2]); an index out of range leaves ?cell unbound', []),
    ('function-in-sequence', 'data-nested', 'SELECT ?s WHERE { ?s :points ?pts FILTER(SEQ(3, 4) IN ?pts) }', [P, F], False, 'SEQ(3, 4) IN ?pts: membership, with a sequence as the needle', []),
    ('function-nested-equality', 'data-nested', 'SELECT ?m ?n WHERE {\n  ?m :matrix ?rows FILTER(?rows = SEQ(SEQ(1, 2, 3), SEQ(4, 5, 6)))\n  ?n :matrix ( ( 1 2 3 ) ( 4 5 6 ) )\n}', [P, F], False, 'a nested sequence compared whole, by = with SEQ(SEQ(…)) and by a pattern', []),
]
# docs/rdf-undef.md §3's table, row by row, and the behaviours of jena-array's TestUndefSlots
UNDEF_QUERIES = [
    ('undef-variable-unbound', 'data-undef', 'SELECT ?s ?a ?b ?c { ?s :p (?a ?b ?c) }', [P, S], False, 'a variable at a slot stays unbound', [f'{JU}.variable_at_a_slot_stays_unbound']),
    ('undef-length-counts', 'data-undef', 'SELECT ?a ?b { :x :p (?a ?b) }', [P, S], False, 'a slot counts: the length still has to match', [f'{JU}.length_still_counts']),
    ('undef-pattern-matches-slot', 'data-undef', 'SELECT ?s ?a ?c { ?s :p (?a undef ?c) }', [P, S], False, 'undef in a pattern matches only a slot', [f'{JU}.undef_in_a_pattern_matches_only_a_slot']),
    ('undef-constant-pattern', 'data-undef', 'SELECT ?s { ?s :p (1 undef 3) }', [P, S], False, 'a sequence term with a slot, written whole', [f'{JU}.undef_in_a_pattern_matches_only_a_slot']),
    ('undef-pattern-case', 'data-undef', 'SELECT ?s { ?s :p (1 UNDEF 3) }', [P, S], False, 'undef in any case', []),
    ('undef-constant-no-match', 'data-undef', 'SELECT ?s { ?s :p (1 2 3) }', [P, S], False, 'a constant does not match a slot', [f'{JU}.constant_does_not_match_a_slot']),
    ('undef-constant-and-variable', 'data-undef', 'SELECT ?s ?c { ?s :p (1 2 ?c) }', [P, S], False, 'a constant does not match a slot, beside a variable', [f'{JU}.constant_does_not_match_a_slot']),
    ('undef-join-bgp-before', 'data-undef', 'SELECT ?s ?a ?b ?c { :v :w ?b . ?s :p (?a ?b ?c) }', [P, S], False, 'a variable bound earlier in the BGP is compatible with a slot; :y holds 2, not 5', [f'{JU}.variable_may_be_bound_at_a_slot_within_a_bgp']),
    ('undef-join-bgp-after', 'data-undef', 'SELECT ?s ?a ?b ?c { ?s :p (?a ?b ?c) . :v :w ?b }', [P, S], False, 'the same with the triple patterns the other way round', [f'{JU}.variable_may_be_bound_at_a_slot_within_a_bgp']),
    ('undef-join-values-before', 'data-undef', 'SELECT ?s ?a ?b ?c { VALUES ?b { 5 } ?s :p (?a ?b ?c) }', [P, S], False, 'VALUES before: the variable joins through the slot', [f'{JU}.variable_may_be_bound_at_a_slot_across_a_join']),
    ('undef-join-values-after', 'data-undef', 'SELECT ?s ?a ?b ?c { ?s :p (?a ?b ?c) VALUES ?b { 5 } }', [P, S], False, 'VALUES after', [f'{JU}.variable_may_be_bound_at_a_slot_across_a_join']),
    ('undef-join-groups', 'data-undef', 'SELECT ?s ?a ?b ?c { { :v :w ?b } { ?s :p (?a ?b ?c) } }', [P, S], False, 'a join of two groups', [f'{JU}.variable_may_be_bound_at_a_slot_across_a_join']),
    ('undef-join-bind', 'data-undef', 'SELECT ?s ?a ?b ?c { BIND(5 AS ?b) ?s :p (?a ?b ?c) }', [P, S], False, 'BIND before', [f'{JU}.variable_may_be_bound_at_a_slot_across_a_join']),
    ('undef-join-value-at-member', 'data-undef', 'SELECT ?s { VALUES ?b { 2 } ?s :p (?a ?b ?c) }', [P, S], False, 'a bound variable matches an equal member, and joins through the slot of :x too', []),
    ('undef-repeated-variable', 'data-undef-repeat', 'SELECT ?s ?v { ?s :p (?v ?v) }', [P, S], False, 'a repeated variable: a slot leaves the binding to the other position', [f'{JU}.repeated_variable']),
    ('undef-gap-stops-at-slot', 'data-undef', 'SELECT ?m { :x :p ( ... ?m ... ) }', [P, G, S], False, 'a gap stops at each slot: three solutions, one with ?m unbound', [f'{JU}.gap_stops_at_each_slot']),
    ('undef-named-gap-keeps-slots', 'data-undef', 'SELECT ?h ?t { :x :p ( ?h ...?t ) }', [P, G, S], False, 'a named gap keeps slots', [f'{JU}.named_gap_keeps_the_slots']),
    ('undef-gap-and-undef-pattern', 'data-undef', 'SELECT ?s ?c { ?s :p ( ... undef ?c ) }', [P, G, S], False, 'undef after a gap: the last member follows a slot', []),
    ('undef-nested', 'data-undef-nested', 'SELECT ?a ?b { ?s :p ( ( ?a ?b ) ) }', [P, S], False, 'a variable at a slot in a nested sequence', [f'{JU}.nested_slot']),
    ('undef-whole-value', 'data-undef', 'SELECT ?v { :x :p ?v }', [P, S], False, 'a variable binds a whole sequence holding a slot', [f'{JU}.sequence_with_slot_as_a_value']),
    ('undef-whole-value-join', 'data-undef', 'SELECT ?s { :x :p ?v . ?s :p ?v }', [P, S], False, 'a sequence holding a slot joins as a value', [f'{JU}.sequence_with_slot_as_a_value']),
    ('undef-filter-not-bound', 'data-undef', 'SELECT ?s { ?s :p (?a ?b ?c) FILTER(!BOUND(?b)) }', [P, S], False, 'a variable at a slot is not bound, so a filter may not assume it', [f'{JU}.filter_on_bound']),
    ('undef-filter-equal', 'data-undef', 'SELECT ?s { ?s :p (?a ?b ?c) FILTER(?b = 2) }', [P, S], False, 'a filter on it is an error at the slot', [f'{JU}.filter_on_value']),
    ('undef-filter-compare', 'data-undef', 'SELECT ?s { ?s :p (?a ?b ?c) FILTER(?b > 0) }', [P, S], False, 'likewise with a comparison', [f'{JU}.filter_on_value']),
    ('undef-optional-after-pattern', 'data-undef', 'SELECT ?s ?b { ?s :p (?a undef ?c) . OPTIONAL { :v :w ?b } }', [P, S], False, 'OPTIONAL after undef in a pattern', [f'{JU}.optional_after_a_slot']),
    ('undef-optional-binds', 'data-undef', 'SELECT ?s ?b { ?s :p (?a ?b ?c) OPTIONAL { :v :w ?b } }', [P, S], False, 'the variable is unbound at :x, so the OPTIONAL is free to bind it', [f'{JU}.optional_after_a_slot']),
    ('undef-index', 'data-undef', "SELECT ?one ?two ?d { :x :p ?s BIND(?s[1] AS ?one) BIND(?s[2] AS ?two) BIND(COALESCE(?s[2], 'none') AS ?d) }", [P, F, S], False, 'an index at a slot is an error, as out of range is', [f'{JU}.index_of_a_slot_is_an_error']),
    ('undef-seqlen-slice', 'data-undef', 'SELECT ?n ?t { :x :p ?s BIND(SEQLEN(?s) AS ?n) BIND(?s[2...3] AS ?t) }', [P, F, S], False, 'SEQLEN counts slots, and slices keep them', [f'{JU}.length_and_slice_keep_the_slots']),
    ('undef-in-member', 'data-undef', 'SELECT ?s { :x :p ?v BIND(:x AS ?s) FILTER(3 IN ?v) }', [P, F, S], False, 'IN looks at members', [f'{JU}.in_skips_slots']),
    ('undef-in-skips-slot', 'data-undef', 'SELECT ?v { :x :p ?v FILTER(2 IN ?v) }', [P, F, S], False, 'IN skips slots: false, not an error', [f'{JU}.in_skips_slots']),
    ('undef-not-in-skips-slot', 'data-undef', 'SELECT ?s { :x :p ?v BIND(:x AS ?s) FILTER(2 NOT IN ?v) }', [P, F, S], False, 'NOT IN likewise', [f'{JU}.in_skips_slots']),
    ('undef-equal-seq', 'data-undef', 'SELECT ?s { ?s :p ?v FILTER(?v = SEQ(1, undef, 3)) }', [P, F, S], False, '= compares slot with slot', [f'{JU}.equality']),
    ('undef-sameterm-seq', 'data-undef', 'SELECT ?s { ?s :p ?v FILTER(sameTerm(?v, SEQ(1, undef, 3))) }', [P, F, S], False, 'sameTerm likewise', [f'{JU}.equality']),
    ('undef-equal-value', 'data-undef', 'SELECT ?s { :x :p ?v BIND(:x AS ?s) FILTER(?v = SEQ(1, 2, 3)) }', [P, F, S], False, '= is false between a slot and a value', [f'{JU}.equality']),
    ('undef-not-equal-value', 'data-undef', 'SELECT ?s { :x :p ?v BIND(:x AS ?s) FILTER(?v != SEQ(1, 2, 3)) }', [P, F, S], False, '!= is true between a slot and a value', [f'{JU}.equality']),
    ('undef-seq-unbound', '-', 'SELECT ?v { BIND(SEQ(1, ?nothing) AS ?v) }', [P, F, S], False, 'SEQ of an unbound variable writes a slot', [f'{JU}.seq_of_an_unbound_variable_is_a_slot']),
    ('undef-seq-literal-slot', '-', 'SELECT ?v { BIND(SEQ(1, undef, SEQ(undef)) AS ?v) }', [P, F, S], False, 'undef as an argument of SEQ, at two depths', [f'{JU}.query_serialization']),
    ('undef-seq-round-trip', 'data-undef', 'SELECT ?v { :x :p (?a ?b ?c) BIND(SEQ(?c, ?b, ?a) AS ?v) }', [P, F, S], False, 'a variable read at a slot writes a slot', [f'{JU}.seq_of_an_unbound_variable_is_a_slot']),
    ('undef-seq-error', '-', 'SELECT ?v { BIND(SEQ(1, 1/0) AS ?v) }', [P, F, S], False, 'any other error in an argument is the error of the SEQ', [f'{JU}.seq_of_any_other_error_is_an_error']),
    ('undef-unnest', 'data-undef', 'SELECT ?m ?i { :x :p ?s UNNEST(?s AS ?m AT ?i) } ORDER BY ?i', [P, U, S], True, 'UNNEST yields a solution at a slot, with the member unbound and the position bound', [f'{JU}.unnest_keeps_the_position']),
    ('undef-unnest-bound', 'data-undef', 'SELECT ?m ?i { :x :p ?s UNNEST(?s AS ?m AT ?i) FILTER(BOUND(?m)) } ORDER BY ?i', [P, U, S], True, 'FILTER(BOUND(?m)) drops the slot', [f'{JU}.unnest_keeps_the_position']),
    ('undef-order-by', 'data-undef', 'SELECT ?s { ?s :p ?v } ORDER BY ?v', [P, S], True, 'a slot sorts before every term', [f'{JU}.order_by_with_slots']),
    ('undef-order-by-members', 'data-undef-order', 'SELECT ?s { ?s :p ?v } ORDER BY ?v', [P, S], True, 'member by member, with a shorter prefix first', []),
    ('undef-values-unchanged', '-', 'SELECT ?x { VALUES ?x { undef } }', [P, S], False, 'VALUES ?x { undef } keeps its meaning', [f'{JU}.values_undef_is_unchanged']),
    ('undef-construct-round-trip', 'data-undef', 'CONSTRUCT { ?s :q (?c ?b ?a) } WHERE { ?s :p (?a ?b ?c) }', [P, S], False, 'an unbound variable in a template sequence writes a slot', [f'{JU}.construct_round_trip']),
    ('undef-construct-template-slot', '-', 'CONSTRUCT { :a :b (undef 1) } WHERE {}', [P, S], False, 'undef in a template', [f'{JU}.template_literal_slot']),
    ('undef-construct-top-level-unbound', '-', 'CONSTRUCT { :a :b ?nothing } WHERE {}', [P, S], False, 'an unbound variable at the top level of a template still drops the triple', [f'{JU}.template_unbound_top_level_still_drops_the_triple']),
]
QUERIES += UNDEF_QUERIES
UPDATES = [
    ('insert-data-sequence', '', 'INSERT DATA { :n :p (4 5) . :n :q () }', [P], 'INSERT DATA inserts sequence terms', [f'{JQ}.update_insert_data_and_delete_data']),
    ('delete-data-sequence', '@prefix : <http://example/> .\n:n :p (4 5) ; :q () .\n', 'DELETE DATA { :n :p (4 5) }', [P], 'DELETE DATA removes the triple with an equal sequence', [f'{JQ}.update_insert_data_and_delete_data']),
    ('delete-where-position', '@prefix : <http://example/> .\n:n :tags ("a" "b") .\n', 'DELETE { ?s :tags ?seq } INSERT { ?s :tag ?t } WHERE { ?s :tags ?seq UNNEST(?seq AS ?t) }', [P, U], 'spread a sequence into repeated properties with UNNEST', []),
    ('undef-insert-data', '', 'INSERT DATA { :s :p (undef 1) }', [P, S], 'INSERT DATA with a slot', [f'{JU}.update']),
    ('undef-delete-data', '@prefix : <http://example/> .\n:s :p (undef 1) , (1 1) .\n', 'DELETE DATA { :s :p (undef 1) }', [P, S], 'DELETE DATA removes the triple with the slot, and not one with a value there', []),
    ('undef-insert-where', '@prefix : <http://example/> .\n:s :p (1 undef) .\n', 'INSERT { ?s :q (?b ?a) } WHERE { ?s :p (?a ?b) }', [P, S], 'INSERT: an unbound variable in a template sequence writes a slot', [f'{JU}.update']),
    ('undef-delete-where', '@prefix : <http://example/> .\n:s :p (1 undef) .\n:t :p (1 2) .\n', 'DELETE { ?s :p (?a undef) } WHERE { ?s :p (?a undef) }', [P, S], 'DELETE with undef in the pattern and the template', []),
]
SYNTAX_BAD = [
    ('bad-sequence-predicate', 'SELECT * { ?s ( ?p ) ?o }', [P], 'a sequence is not a predicate'),
    ('bad-slice-colon', 'SELECT * { ?s :p ?o BIND(?o[2:4] AS ?x) }', [P, F], 'a slice is [m...n]: in [2:4], :4 is a prefixed name'),
    ('bad-slice-no-ends', 'SELECT * { ?s :p ?o BIND(?o[...] AS ?x) }', [P, F], 'a slice needs at least one end'),
    ('bad-gap-in-template', 'CONSTRUCT { ?s :p ( ?a ... ) } WHERE { ?s :p ?a }', [P, G], 'a gap is a pattern: a template builds a sequence and may not hold one'),
    ('bad-unnest-without-as', 'SELECT * { ?s :p ?seq UNNEST(?seq ?x) }', [P, U], 'UNNEST binds its member with AS'),
    ('bad-old-position-pattern', 'SELECT * { ?s :p ((?e))[1] }', [P], 'the former ((e))[i] position pattern is no longer syntax'),
    ('undef-bad-object', 'SELECT * { ?s :p undef }', [P, S], 'a slot is only a member of a sequence, not an object'),
    ('undef-bad-subject', 'SELECT * { undef :p ?o }', [P, S], 'nor a subject'),
    ('undef-bad-predicate', 'SELECT * { ?s undef ?o }', [P, S], 'nor a predicate'),
    ('undef-bad-bind', 'SELECT * { BIND(undef AS ?x) }', [P, S], 'nor an expression'),
    ('undef-bad-filter', 'SELECT * { ?s :p ?o FILTER(?o = undef) }', [P, S], 'nor an operand'),
    ('undef-bad-function-argument', 'SELECT * { BIND(STR(undef) AS ?x) }', [P, S], 'only SEQ takes it as an argument'),
    ('undef-bad-template-object', 'CONSTRUCT { ?s :p undef } WHERE { ?s :p ?o }', [P, S], 'nor an object in a template'),
]
# positive syntax tests of the array syntax's lexing and expression forms (docs/array-syntax.md §5); not evaluated
SYNTAX_GOOD = [
    ('syntax-gap-lexing', 'SELECT * { ?s :p ( 1... ) . ?s :q ( :a... ) . ?s :r ( :a...b ) }', [P, G], '1... and :a... are a member then a gap; :a...b is one prefixed name'),
    ('syntax-gap-named-or-not', 'SELECT * { ?s :p ( ?a ... ?b ) . ?s :q ( ?a ...?b ) }', [P, G], '( ?a ... ?b ) is a gap then a member; ( ?a ...?b ) is a named gap'),
    ('syntax-gaps-nested', 'SELECT * { ?m :matrix ( ... ( ... ?x ... ) ... ) }', [P, G], 'gaps nest'),
    ('syntax-slice-forms', 'SELECT * { ?s :p ?o BIND(?o[2...4] AS ?x) BIND(?o[...SEQLEN(?o) - 1] AS ?y) BIND(?o[2...][1] AS ?z) }', [P, F], 'slices with both ends, with one end, and an index of a slice'),
    ('syntax-in-list-and-sequence', 'SELECT * { ?s :p ?o FILTER(?o IN (?a) && ?o IN ?a && ?o NOT IN SEQ(1, 2) && 3 IN ?a[1]) }', [P, F], 'IN ( … ) keeps its SPARQL 1.1 meaning; IN ?seq, NOT IN SEQ(…) and IN ?seq[i] test membership'),
    ('syntax-order-by-index', 'SELECT ?x { ?s :p ?x } ORDER BY (?x[1])', [P, F], 'an index in ORDER BY needs parentheses'),
    ('undef-syntax-prefix', 'PREFIX undef: <http://example/>\nSELECT * { undef:s undef:p ( undef:o undef undef: ) }', [P, S], 'undef:x is a prefixed name and undef alone a slot'),
    ('undef-syntax-nested', 'SELECT * { ?s :p ( ( undef ?a ) ... UNDEF ) }', [P, G, S], 'a slot at depth, beside a gap, in any case'),
    ('undef-syntax-template', 'CONSTRUCT { ?s :q ( undef ?c ) } WHERE { ?s :p ?c }', [P, S], 'a slot in a template'),
]


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def write(path, text):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return False
    if CHECK:
        raise SystemExit(f'{path.relative_to(ROOT)} would change')
    path.write_text(text, encoding='utf-8')
    return True


def write_graph(path, text):
    """write an expected graph unless the file already holds an isomorphic one (jena-array's blank node order varies)."""
    full = ROOT / path
    if full.exists() and ra.isomorphic(ra.parse(full.read_text(encoding='utf-8')), ra.parse(text)):
        return False
    return write(path, text)


def jena(*args):
    cp = (JT / 'cp.txt').read_text().strip()
    return run([JAVA, '-cp', f'{JT}:{cp}', 'JenaArray', *args])


def relabel(quads):
    """blank nodes as _:b0, _:b1, ... in order of appearance."""
    m = {}

    def lab(t):
        if t is None:
            return None
        if t[0] == 'bnode':
            m.setdefault(t, ra.bnode(f'b{len(m)}'))
            return m[t]
        if t[0] == 'seq':
            return ra.seq(lab(e) for e in t[1])
        if t[0] == 'triple':
            return ('triple',) + tuple(lab(x) for x in t[1:])
        return t
    return [tuple(lab(t) for t in q) for q in quads]


def build_syntax(problems, manifests, dups, notes):
    for d, ext, typ, cases in SYNTAXES:
        entries = []
        for name, text, kind, comment, dup in cases:
            f = ROOT / 'rdf' / d / (name + ext)
            write(f.relative_to(ROOT), text + '\n')
            base = f'{BASE}rdf/{d}/{name}{ext}'
            j = jena('parse', f, base)
            if JENA_ONLY and name.startswith('undef-'):
                n = None
                notes.append(f'{d}/{name}')
            else:
                n = run(['node', TOOLS / 'parse-n3-array.js', f, base])
            if n is None:
                if (kind == 'bad') != (j.returncode != 0):
                    problems.append(f'{d}/{name}: jena-array {"accepts" if kind == "bad" else "rejects"} it')
                    continue
                if kind == 'bad':
                    entries.append((name, f'rdft:Test{typ}NegativeSyntax', comment, f'<{name}{ext}>', None))
                elif kind == 'eval':
                    rext = '.nq' if ext in ('.trig', '.nq') else '.nt'
                    write_graph(f.with_suffix(rext).relative_to(ROOT), ra.write(relabel(ra.parse(j.stdout))))
                    entries.append((name, f'rdft:Test{typ}Eval', comment, f'<{name}{ext}>', f'<{name}{rext}>'))
                else:
                    entries.append((name, f'rdft:Test{typ}PositiveSyntax', comment, f'<{name}{ext}>', None))
            elif kind == 'bad':
                if j.returncode == 0 or n.returncode == 0:
                    problems.append(f'{d}/{name}: not rejected by ' + ' and '.join(x for x, r in (('jena-array', j), ('N3.js-array', n)) if r.returncode == 0))
                entries.append((name, f'rdft:Test{typ}NegativeSyntax', comment, f'<{name}{ext}>', None))
            else:
                if j.returncode or n.returncode:
                    problems.append(f'{d}/{name}: rejected by ' + ' and '.join(x for x, r in (('jena-array', j), ('N3.js-array', n)) if r.returncode))
                    continue
                qj, qn = ra.parse(j.stdout), ra.parse(n.stdout)
                if not ra.isomorphic(qj, qn):
                    problems.append(f'{d}/{name}: jena-array and N3.js-array read different graphs')
                    continue
                if kind == 'eval':
                    rext = '.nq' if ext in ('.trig', '.nq') else '.nt'
                    write_graph(f.with_suffix(rext).relative_to(ROOT), ra.write(relabel(qj)))
                    entries.append((name, f'rdft:Test{typ}Eval', comment, f'<{name}{ext}>', f'<{name}{rext}>'))
                else:
                    entries.append((name, f'rdft:Test{typ}PositiveSyntax', comment, f'<{name}{ext}>', None))
            if dup:
                dups.append({'test': f'rdf/{d}/manifest#{name}', 'duplicates': dup})
        manifests.append(('rdf/' + d, syntax_manifest(d, entries)))


def syntax_manifest(d, entries):
    s = f'''@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mf:   <http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#> .
@prefix rdft: <http://www.w3.org/ns/rdftest#> .
@prefix ra:   <https://rdf-array.github.io/rdf-array/vocab#> .

# Generated by bin/build.py -- edit the case table there.
<> a mf:Manifest ;
    rdfs:label "rdf-array {d} contrib tests" ;
    mf:assumedTestBase <{BASE}rdf/{d}/> ;
    mf:entries (
''' + ''.join(f'        <#{n}>\n' for n, *_ in entries) + '    ) .\n'
    for name, typ, comment, action, result in entries:
        s += f'''
<#{name}> a {typ} ;
    mf:name "{name}" ;
    rdfs:comment "{comment}" ;
    mf:requires ra:Sequences{", ra:UndefSlots" if name.startswith("undef-") else ""} ;
    mf:action {action} ;
''' + (f'    mf:result {result} ;\n' if result else '') + '    .\n'
    return s


def comunica(query, data, media):
    return run(['node', TOOLS / 'comunica-array-query.js', query, data, media])


def build_sparql(problems, manifests, dups, notes):
    for name, text in DATA.items():
        write(f'sparql/eval/{name}.ttl', text)
    entries = []
    for name, data, query, feats, ordered, comment, dup in QUERIES:
        q = ROOT / f'sparql/eval/{name}.rq'
        write(q.relative_to(ROOT), X + query + '\n')
        dfile = ROOT / f'sparql/eval/{data}.ttl' if data != '-' else None
        r = jena('query', q, dfile if dfile else '-')
        if r.returncode:
            problems.append(f'sparql/eval/{name}: jena-array: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "failed"}')
            continue
        construct = query.startswith('CONSTRUCT')
        if construct:
            res = q.with_suffix('.nt')
            write_graph(res.relative_to(ROOT), ra.write(relabel(ra.parse(r.stdout))))
        else:
            res = q.with_suffix('.srj')
            if not (res.exists() and sr.same(res.read_text(encoding='utf-8'), r.stdout, ordered)):  # row order of an unordered query varies
                write(res.relative_to(ROOT), json.dumps(json.loads(r.stdout), indent=2) + '\n')
        if (feats == [P] or S in feats) and not (JENA_ONLY and S in feats):  # beyond the slots, comunica-array is checked on sequence patterns, ordering, CONSTRUCT and results
            c = comunica(q, dfile if dfile else '-', 'application/n-triples' if construct else 'application/sparql-results+json')
            if c.returncode:
                problems.append(f'sparql/eval/{name}: comunica-array: {c.stderr.strip()[:200]}')
            elif construct and not ra.isomorphic(ra.parse(c.stdout), ra.parse(r.stdout)):
                problems.append(f'sparql/eval/{name}: comunica-array constructs a different graph')
            elif not construct and not sr.same(r.stdout, c.stdout, ordered):
                problems.append(f'sparql/eval/{name}: comunica-array gives different results')
        else:
            notes.append(name)
        entries.append(('mf:QueryEvaluationTest', name, comment, feats, f'[ qt:query <{q.name}> ' + (f'; qt:data <{data}.ttl> ' if dfile else '') + ']', f'<{res.name}>'))
        if dup:
            dups.append({'test': f'sparql/eval/manifest#{name}', 'duplicates': dup})
    # a named graph: the query names no graph, so the graph's IRI does not reach the results
    q, dfile = ROOT / 'sparql/eval/undef-graph.rq', ROOT / 'sparql/eval/data-undef.ttl'
    write(q.relative_to(ROOT), X + 'SELECT ?a ?b { GRAPH ?g { :v :w ?b . :x :p (?a ?b ?c) } }\n')
    r = jena('query', q, '-', dfile)
    if r.returncode:
        problems.append(f'sparql/eval/undef-graph: jena-array: {r.stderr.strip()[-200:]}')
    else:
        write('sparql/eval/undef-graph.srj', json.dumps(json.loads(r.stdout), indent=2) + '\n')
    entries.append(('mf:QueryEvaluationTest', 'undef-graph', 'a variable joins through a slot inside GRAPH', [P, S], f'[ qt:query <{q.name}> ; qt:graphData <{dfile.name}> ]', '<undef-graph.srj>'))
    dups.append({'test': 'sparql/eval/manifest#undef-graph', 'duplicates': [f'{JU}.quads']})
    manifests.append(('sparql/eval', sparql_manifest('eval', entries)))
    entries = []
    for name, pre, update, feats, comment, dup in UPDATES:
        u = ROOT / f'sparql/update/{name}.ru'
        write(u.relative_to(ROOT), X + update + '\n')
        pre_f = ROOT / f'sparql/update/{name}-pre.ttl'
        write(pre_f.relative_to(ROOT), pre or '# empty\n')
        r = jena('update', u, pre_f)
        if r.returncode:
            problems.append(f'sparql/update/{name}: jena-array: {r.stderr.strip()[-200:]}')
            continue
        post = ROOT / f'sparql/update/{name}-post.nt'
        write_graph(post.relative_to(ROOT), ra.write(relabel(ra.parse(r.stdout))))
        entries.append(('mf:UpdateEvaluationTest', name, comment, feats, f'[ ut:request <{u.name}> ; ut:data <{pre_f.name}> ]', f'[ ut:data <{post.name}> ]'))
        if dup:
            dups.append({'test': f'sparql/update/manifest#{name}', 'duplicates': dup})
        if feats != [P]:
            notes.append(name)
    manifests.append(('sparql/update', sparql_manifest('update', entries)))
    entries = []
    for name, query, feats, comment in SYNTAX_BAD:
        q = ROOT / f'sparql/syntax-query/{name}.rq'
        write(q.relative_to(ROOT), X + query + '\n')
        if jena('inspect', q).stdout.startswith('none') or not jena('inspect', q).stdout.startswith('error'):
            problems.append(f'sparql/syntax-query/{name}: jena-array accepts it')
        if (feats == [P] or (S in feats and not JENA_ONLY)) and comunica(q, '-', 'application/sparql-results+json').returncode == 0:
            problems.append(f'sparql/syntax-query/{name}: comunica-array accepts it')
        entries.append(('mf:NegativeSyntaxTest11', name, comment, feats, f'<{q.name}>', None))
    for name, query, feats, comment in SYNTAX_GOOD:
        q = ROOT / f'sparql/syntax-query/{name}.rq'
        write(q.relative_to(ROOT), X + query + '\n')
        if jena('inspect', q).stdout.startswith('error'):
            problems.append(f'sparql/syntax-query/{name}: jena-array rejects it')
        entries.append(('mf:PositiveSyntaxTest11', name, comment, feats, f'<{q.name}>', None))
    for name, data, query, feats, ordered, comment, dup in QUERIES:  # every evaluation query is also a positive syntax test
        entries.append(('mf:PositiveSyntaxTest11', 'syntax-' + name, comment, feats, f'<../eval/{name}.rq>', None))
    manifests.append(('sparql/syntax-query', sparql_manifest('syntax-query', entries)))
    # one query's results in the four result formats, written by comunica-array, equal to jena-array's
    q = ROOT / 'sparql/eval/sequence-whole-binding.rq'
    entries = []
    jres = jena('query', q, ROOT / 'sparql/eval/data.ttl').stdout
    for media, ext, typ in (('application/sparql-results+json', '.srj', 'mf:QueryEvaluationTest'), ('application/sparql-results+xml', '.srx', 'mf:QueryEvaluationTest'),
                            ('text/csv', '.csv', 'mf:CSVResultFormatTest'), ('text/tab-separated-values', '.tsv', 'mf:QueryEvaluationTest')):
        c = comunica(q, ROOT / 'sparql/eval/data.ttl', media)
        if c.returncode:
            problems.append(f'sparql/results{ext}: comunica-array: {c.stderr[:200]}')
            continue
        if ext == '.srj' and not sr.same(jres, c.stdout, True):
            problems.append('sparql/results: comunica-array JSON differs from jena-array JSON')
        out = c.stdout
        if ext == '.srj':  # comunica adds a "metadata" member that SPARQL Results JSON does not define
            out = re.sub(r',\s*"metadata":\s*\{[^{}]*\}\s*\}\s*$', '}', out)
        write(f'sparql/results/sequences{ext}', out if out.endswith('\n') else out + '\n')
        entries.append((typ, f'results{ext.replace(".", "-")}', f'sequence bindings in the {media} results format', [P, 'ra:SequenceResults'],
                        '[ qt:query <../eval/sequence-whole-binding.rq> ; qt:data <../eval/data.ttl> ]', f'<sequences{ext}>'))
    # the slot in the two formats that spell one: { "type": "undef" } and <unbound/>
    q = ROOT / 'sparql/results/undef-values.rq'
    dfile = ROOT / 'sparql/eval/data-undef.ttl'
    write(q.relative_to(ROOT), X + 'SELECT ?s ?v { ?s :p ?v } ORDER BY ?s\n')
    for fmt, media, ext in (('json', 'application/sparql-results+json', '.srj'), ('xml', 'application/sparql-results+xml', '.srx')):
        r = jena('query-format', fmt, q, dfile)
        if r.returncode:
            problems.append(f'sparql/results/undef-values{ext}: jena-array: {r.stderr.strip()[-200:]}')
            continue
        write(f'sparql/results/undef-values{ext}', r.stdout)
        if ext == '.srj' and not JENA_ONLY:
            c = comunica(q, dfile, media)
            if c.returncode or not sr.same(r.stdout, c.stdout, True):
                problems.append('sparql/results/undef-values: comunica-array JSON differs from jena-array JSON')
        entries.append(('mf:QueryEvaluationTest', f'undef-results{ext.replace(".", "-")}', f'a slot in a sequence in the {media} results format', [P, S, 'ra:SequenceResults'],
                        f'[ qt:query <{q.name}> ; qt:data <../eval/data-undef.ttl> ]', f'<undef-values{ext}>'))
    dups.append({'test': 'sparql/results/manifest#undef-results-srj', 'duplicates': [f'{JU}.results_json']})
    dups.append({'test': 'sparql/results/manifest#undef-results-srx', 'duplicates': [f'{JU}.results_xml']})
    manifests.append(('sparql/results', sparql_manifest('results', entries)))
    dups.append({'test': 'sparql/results/manifest#results-srj', 'duplicates': ['comunica-array packages/actor-query-result-serialize-sparql-json test', 'sparqljson-parse-array test/SparqlJsonParser-test.ts "rdf-array sequences"']})
    dups.append({'test': 'sparql/results/manifest#results-srx', 'duplicates': ['comunica-array packages/actor-query-result-serialize-sparql-xml test', 'sparqlxml-parse-array test/SparqlXmlParser-test.ts "rdf-array sequences"']})
    dups.append({'test': 'sparql/results/manifest#results-csv', 'duplicates': ['comunica-array packages/actor-query-result-serialize-sparql-csv test']})


def sparql_manifest(d, entries):
    s = f'''@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mf:   <http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#> .
@prefix qt:   <http://www.w3.org/2001/sw/DataAccess/tests/test-query#> .
@prefix ut:   <http://www.w3.org/2009/sparql/tests/test-update#> .
@prefix ra:   <https://rdf-array.github.io/rdf-array/vocab#> .

# Generated by bin/build.py -- edit the case table there.
<> a mf:Manifest ;
    rdfs:label "SPARQL-array {d} contrib tests" ;
    mf:entries (
''' + ''.join(f'        <#{e[1]}>\n' for e in entries) + '    ) .\n'
    for typ, name, comment, feats, action, result in entries:
        s += f'''
<#{name}> a {typ} ;
    mf:name "{name}" ;
    rdfs:comment "{comment}" ;
    mf:requires {", ".join(feats)} ;
    mf:action {action} ;
''' + (f'    mf:result {result} ;\n' if result else '') + '    .\n'
    return s


def main():
    problems, manifests, dups, notes = [], [], [], []
    build_syntax(problems, manifests, dups, notes)
    build_sparql(problems, manifests, dups, notes)
    if problems:
        raise SystemExit('cross-check failed:\n  ' + '\n  '.join(problems))
    for d, text in manifests:
        write(f'{d}/manifest.ttl', text)
    write('manifest.ttl', '''@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mf:   <http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#> .

# Generated by bin/build.py.
<> a mf:Manifest ;
    rdfs:label "rdf-array contrib tests: RDF syntaxes and SPARQL" ;
    mf:include (
''' + ''.join(f'        <{d}/manifest.ttl>\n' for d, _ in manifests) + '    ) .\n')
    write('duplicates.json', json.dumps({'suite': 'rdf-tests-contrib', 'tests': dups}, indent=1) + '\n')
    n_syntax = sum(len(c) for *_, c in SYNTAXES)
    print(f'{n_syntax} RDF syntax tests (jena-array = N3.js-array), {len(QUERIES)} SPARQL evaluation, {len(UPDATES)} update, '
          f'{len(SYNTAX_BAD) + len(SYNTAX_GOOD) + len(QUERIES)} syntax and 6 results-format tests; jena-array only (proposed syntax): {", ".join(notes)}')


if __name__ == '__main__':
    main()
