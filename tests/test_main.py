# -*- coding: utf-8 -*-
from __future__ import print_function, division

import ast
import contextlib
import dis
import inspect
import json
import os
import re
import sys
import tempfile
import time
import types
import unittest
from collections import defaultdict, namedtuple
from random import shuffle

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tests.utils import tester, subscript_item, in_finally, start_position, end_position

PYPY = 'pypy' in sys.version.lower()

from executing import Source, only, NotOneValueFound
from executing.executing import PY3, get_instructions, function_node_types

from executing._exceptions import VerifierFailure, KnownIssue

if sys.version_info >= (3,11):
    from tests.deadcode import Deadcode

if eval("0"):
    global_never_defined = 1


def calling_expression():
    frame = inspect.currentframe().f_back.f_back
    return Source.executing(frame).node


def ast_dump(*args, **kwargs):
    if sys.version_info < (3, 9):
        del kwargs["indent"]
    return ast.dump(*args, **kwargs)


class TestStuff(unittest.TestCase):

    # noinspection PyTrailingSemicolon
    def test_semicolons(self):
        # @formatter:off
        tester(1); tester(2); tester(3)
        tester(9
               ); tester(
            8); tester(
            99
        ); tester(33); tester([4,
                               5, 6, [
                                7]])
        # @formatter:on

    def test_decorator(self):
        @empty_decorator  # 0
        @decorator_with_args(tester('123'), x=int())  # 1
        @tester(list(tuple([1, 2])))  # 2!
        @tester(  # 3!
            list(
                tuple(
                    [3, 4])),
            )
        @empty_decorator  # 4
        @decorator_with_args(  # 5
            str(),
            x=int())
        @tester(list(tuple([5, 6])))  # 6!
        @tester(list(tuple([7, 8])))  # 7!
        @empty_decorator
        @decorator_with_args(tester('sdf'), x=tester('123234'))
        def foo():
            pass

        tester.check_decorators([7, 6, 3, 2])

        empty_decorator.tester = tester

        @empty_decorator
        @tester
        @empty_decorator
        @tester.qwe
        @empty_decorator
        @tester("1")
        @empty_decorator.tester("2")
        @empty_decorator
        def foo2(_=tester("3"), __=tester("4")):
            pass

        tester.check_decorators([6, 5, 3, 1])

        @tester
        @empty_decorator
        @tester.qwe
        @empty_decorator
        @tester("11")
        @empty_decorator.tester("22")
        @empty_decorator
        class foo3(tester("5") and list):
            pass

        tester.check_decorators([5, 4, 2, 0])

        # this checks a spectial case for 3.11
        # TODO: format strings are not valid syntax before 3.6. how can it be tested?
        # TODO: this test fails also for 3.6 3.7 3.8 and 3.9 for unknown reason
        #
        # @tester.qwe()
        # def foo4(log_dir=f"test{tester.attr}"):
        #     pass

        # tester.check_decorators([0])

        class Foo(object):
            @tester
            @tester
            @empty_decorator
            @tester.qwe
            @empty_decorator
            def foo(self):
                super(Foo, self)

                class Bar:
                    @tester
                    @empty_decorator
                    @tester.qwe
                    @empty_decorator
                    def bar(self):
                        pass

        Foo().foo()
        tester.check_decorators([3, 1, 0, 2, 0])

    def not_found_prior_311(self):
        if sys.version_info >= (3, 11):
            from contextlib import nullcontext

            return nullcontext()
        else:
            return self.assertRaises(NotOneValueFound)

    def test_setattr(self):
        tester.x = 1
        tester.y, tester.z = tester.foo, tester.bar = tester.spam = 1, 2

        tester.test_set_private_attrs()

        for tester.a, (tester.b, tester.c) in [(1, (2, 3))]:
            pass

        str([None for tester.a, (tester.b, tester.c) in [(1, (2, 3))]])

        with self.not_found_prior_311():
            tester.a = tester.a = 1

        with self.not_found_prior_311():
            tester.a, tester.a = 1, 2

    def test_setitem(self):
        tester['x'] = 1
        tester[:2] = 3
        tester['a'], tester.b = 8, 9

        with self.not_found_prior_311():
            tester['a'] = tester['b'] = 1

        with self.not_found_prior_311():
            tester['a'], tester['b'] = 1, 2

    def test_comprehensions(self):
        # Comprehensions can be separated if they contain different names
        str([{tester(x) for x in [1]}, {tester(y) for y in [1]}])
        # or are on different lines
        str([{tester(x) for x in [1]},
             {tester(x) for x in [1]}])
        # or are of different types
        str([{tester(x) for x in [1]}, list(tester(x) for x in [1])])
        # but not if everything is the same
        # noinspection PyTypeChecker
        if sys.version_info >= (3, 11):
            str([{tester(x) for x in [1]}, {tester(x) for x in [2]}])
        else:
            with self.assertRaises(NotOneValueFound):
                str([{tester(x) for x in [1]}, {tester(x) for x in [2]}])

    def test_lambda(self):
        self.assertEqual(
            (lambda x: (tester(x), tester(x)))(tester(3)),
            (3, 3),
        )
        (lambda: (lambda: tester(1))())()
        self.assertEqual(
            (lambda: [tester(x) for x in tester([1, 2])])(),
            [1, 2],
        )

    def test_closures_and_nested_comprehensions(self):
        x = 1
        # @formatter:off
        str({tester(a+x): {tester(b+x): {tester(c+x) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})

        def foo():
            y = 2
            str({tester(a+x): {tester(b+x): {tester(c+x) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})
            str({tester(a+y): {tester(b+y): {tester(c+y) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})
            str({tester(a+x+y): {tester(b+x+y): {tester(c+x+y) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})

            def bar():
                z = 3
                str({tester(a+x): {tester(b+x): {tester(c+x) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})
                str({tester(a+y): {tester(b+y): {tester(c+y) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})
                str({tester(a+x+y): {tester(b+x+y): {tester(c+x+y) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})
                str({tester(a+x+y+z): {tester(b+x+y+z): {tester(c+x+y+z) for c in tester([1, 2])} for b in tester([3, 4])} for a in tester([5, 6])})

            bar()

        foo()
        # @formatter:on

    def test_indirect_call(self):
        dict(x=tester)['x'](tester)(3, check_func=False)

    def test_compound_statements(self):
        with self.assertRaises(TypeError):
            try:
                for _ in tester([1, 2, 3]):
                    while tester(0):
                        pass
                    else:
                        tester(4)
                else:
                    tester(5)
                    raise ValueError
            except tester(ValueError):
                tester(9)
                raise TypeError
            finally:
                tester(10)

        # PyCharm getting confused somehow?
        # noinspection PyUnreachableCode
        str()

        with self.assertRaises(tester(Exception)):
            if tester(0):
                pass
            elif tester(0):
                pass
            elif tester(1 / 0):
                pass

    def test_generator(self):
        def gen():
            for x in [1, 2]:
                yield tester(x)

        gen2 = (tester(x) for x in tester([1, 2]))

        assert list(gen()) == list(gen2) == [1, 2]

    def test_future_import(self):
        print(1 / 2)
        tester(4)

    def test_many_calls(self):
        node = None
        start = time.time()
        for i in range(10000):
            new_node = Source.executing(inspect.currentframe()).node
            if node is None:
                node = new_node
            else:
                self.assertIs(node, new_node)
        self.assertLess(time.time() - start, 1)

    def test_many_source_for_filename_calls(self):
        source = None
        start = time.time()
        for i in range(10000):
            new_source = Source.for_filename(__file__)
            if source is None:
                source = new_source
                self.assertGreater(len(source.lines), 700)
                self.assertGreater(len(source.text), 7000)
            else:
                self.assertIs(source, new_source)
        self.assertLess(time.time() - start, 1)

    def test_decode_source(self):
        def check(source, encoding, exception=None, matches=True):
            encoded = source.encode(encoding)
            if exception:
                with self.assertRaises(exception):
                    Source.decode_source(encoded)
            else:
                decoded = Source.decode_source(encoded)
                if matches:
                    self.assertEqual(decoded, source)
                else:
                    self.assertNotEqual(decoded, source)

        check(u'# coding=utf8\né', 'utf8')
        check(u'# coding=gbk\né', 'gbk')

        check(u'# coding=utf8\né', 'gbk', exception=UnicodeDecodeError)
        check(u'# coding=gbk\né', 'utf8', matches=False)

        # In Python 3 the default encoding is assumed to be UTF8
        if PY3:
            check(u'é', 'utf8')
            check(u'é', 'gbk', exception=SyntaxError)

    def test_multiline_strings(self):
        tester('a')
        tester('''
            ab''')
        tester('''
                    abc
                    def
                    '''
               )
        str([
            tester(
                '''
                123
                456
                '''
            ),
            tester(
                '''
                345
                456786
                '''
            ),
        ])
        tester(
            [
                '''
                123
                456
                '''
                '''
                345
                456786
                '''
                ,
                '''
                123
                456
                ''',
                '''
                345
                456786
                '''
            ]
        )

    def test_multiple_statements_on_one_line(self):
        if tester(1): tester(2)
        for _ in tester([1, 2]): tester(3)

    def assert_qualname(self, func, qn, check_actual_qualname=True):
        qualname = Source.for_filename(__file__).code_qualname(func.__code__)
        self.assertEqual(qn, qualname)
        if PY3 and check_actual_qualname:
            self.assertEqual(qn, func.__qualname__)
        self.assertTrue(qn.endswith(func.__name__))

    def test_qualname(self):
        self.assert_qualname(C.f, 'C.f')
        self.assert_qualname(C.D.g, 'C.D.g')
        self.assert_qualname(f, 'f')
        self.assert_qualname(f(), 'f.<locals>.g')
        self.assert_qualname(C.D.h(), 'C.D.h.<locals>.i.<locals>.j')
        self.assert_qualname(lamb, '<lambda>')
        foo = lambda_maker()
        self.assert_qualname(foo, 'lambda_maker.<locals>.foo')
        self.assert_qualname(foo.x, 'lambda_maker.<locals>.<lambda>')
        self.assert_qualname(foo(), 'lambda_maker.<locals>.foo.<locals>.<lambda>')
        self.assert_qualname(foo()(), 'lambda_maker.<locals>.foo.<locals>.<lambda>', check_actual_qualname=False)

    def test_extended_arg(self):
        source = 'tester(6)\n%s\ntester(9)' % list(range(66000))
        _, filename = tempfile.mkstemp()
        code = compile(source, filename, 'exec')
        with open(filename, 'w') as outfile:
            outfile.write(source)
        exec(code)

    def test_only(self):
        for n in range(5):
            gen = (i for i in range(n))
            if n == 1:
                self.assertEqual(only(gen), 0)
            else:
                with self.assertRaises(NotOneValueFound):
                    only(gen)

    def test_invalid_python(self):
        path = os.path.join(os.path.dirname(__file__), 'not_code.txt', )
        source = Source.for_filename(path)
        self.assertIsNone(source.tree)

    def test_executing_methods(self):
        frame = inspect.currentframe()
        executing = Source.executing(frame)
        self.assertEqual(executing.code_qualname(), 'TestStuff.test_executing_methods')
        text = 'Source.executing(frame)'
        self.assertEqual(executing.text(), text)
        start, end = executing.text_range()
        self.assertEqual(executing.source.text[start:end], text)

    def test_attr(self):
        c = C()
        c.x = c.y = tester
        str((c.x.x, c.x.y, c.y.x, c.y.y, c.x.asd, c.y.qwe))

    def test_store_attr_multiline(self):
        if sys.version_info >= (3,11):
            tester.x \
            .y = 1

            tester.x. \
            y = 2

            tester \
            .x.y = 3

            tester. \
            x.y = 4

            tester \
            . \
            x \
            . \
            y \
            = \
            4

            tester \
           . \
          x \
         . \
        y \
       = \
      4
            (tester
           .
          x
         .
        y
       ) = 4

    def test_del_attr_multiline(self):
        if sys.version_info >= (3,11):
            del tester.x \
            .y

            del tester.x. \
            y

            del tester \
            .x.y

            del tester. \
            x.y

    def test_method_call_multiline(self):
        if sys.version_info >= (3,11):
            tester.method(
                tester,
            ).other_method(
                5
            )

            tester.a().b()\
                .c().d()\
                .e(tester.x1().x2()
                .y1()
                .y2()).foo.bar.spam()

            assert 5== tester.a\
                    (tester).\
                    b(5)

    def test_call_things(self):
        # call things which are no methods or functions
        if sys.version_info >= (3,11):
            tester[5](5)
            tester.some[5](5)

            (tester+tester)(2)

            tester(tester)(5)
            tester.some(tester)(5)

    def test_traceback(self):
        try:
            134895 / 0
        except:
            tb = sys.exc_info()[2]
            ex = Source.executing(tb)
            self.assertTrue(isinstance(ex.node, ast.BinOp))
            self.assertEqual(ex.text(), "134895 / 0")

    def test_retry_cache(self):
        _, filename = tempfile.mkstemp()

        def check(x):
            source = 'tester(6)\n%s\ntester(9)' % list(range(x))
            code = compile(source, filename, 'exec')
            with open(filename, 'w') as outfile:
                outfile.write(source)
            exec(code, globals(), locals())

        check(3)
        check(5)

    @contextlib.contextmanager
    def assert_name_error(self):
        try:
            yield
        except NameError as e:
            tb = sys.exc_info()[2]
            ex = Source.executing(tb.tb_next)
            self.assertEqual(type(ex.node), ast.Name)
            self.assertIn(ex.node.id, str(e))
            self.assertEqual(ex.text(), ex.node.id)
        else:
            self.fail("NameError not raised")

    def test_names(self):
        with self.assert_name_error():
            self, completely_nonexistent  # noqa

        with self.assert_name_error():
            self, global_never_defined  # noqa

        with self.assert_name_error():
            self, local_not_defined_yet  # noqa

        local_not_defined_yet = 1  # noqa

        def foo():
            with self.assert_name_error():
                self, closure_not_defined_yet  # noqa

        foo()
        closure_not_defined_yet = 1  # noqa

    def test_with(self):
        if sys.version_info >= (3, 11):
            with tester:
                pass

            with tester as a, tester() as b, tester.tester() as c:
                a(b(c()))

    def test_listcomp(self):
        if sys.version_info >= (3, 11):
            result = [calling_expression() for e in [1]]
            self.assertIsInstance(result[0], ast.ListComp)

    def test_decorator_cache_instruction(self):
        frame = inspect.currentframe()

        def deco(f):
            assert f.__name__ == "foo"
            ex = Source.executing(frame)
            assert isinstance(ex.node, ast.FunctionDef)
            assert isinstance(ex.decorator, ast.Name)

        @deco
        def foo():
            pass


def is_unary_not(node):
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)


class TimeOut(Exception):
    pass


def dump_source(source, start, end, context=4, file=sys.stdout):
    print("source code:", file=file)
    start = max(start.lineno - 5, 0)
    num = start + 1
    for line in source.splitlines()[start : end.lineno + 5]:
        print("%s: %s" % (str(num).rjust(4), line), file=file)
        num += 1



def is_annotation(node):
    if isinstance(node, ast.AnnAssign):
        return True

    x = node
    while hasattr(x, "parent"):
        # check for annotated function arguments
        # def foo(i: int) -> int
        #            ^^^
        if isinstance(x.parent, ast.arg) and x.parent.annotation == x:
            return True

        # check for function return value annotation
        # def foo() -> int
        #              ^^^
        if isinstance(x.parent, ast.FunctionDef) and x.parent.returns == x:
            return True

        # annotation itself
        # a: int = 5
        #    ^^^
        if isinstance(x.parent, ast.AnnAssign) and x.parent.annotation == x:
            return True

        # target of an annotation without value
        # a: int
        # ^
        if (
            isinstance(x.parent, ast.AnnAssign)
            and x.parent.target == x
            and x.parent.value == None
        ):
            return True
        
        x = x.parent

    return False


@unittest.skipUnless(
    os.getenv('EXECUTING_SLOW_TESTS'),
    'These tests are very slow, enable them explicitly',
)
class TestFiles(unittest.TestCase):

    maxDiff = None

    def test_sample_files(self):
        """
        * test all files in the samples folder
        * if everything is ok create sample_results file or compare with an existing
        """
        self.start_time = time.time()
        root_dir = os.path.dirname(__file__)
        samples_dir = os.path.join(root_dir, 'samples')
        result_filename = PYPY * 'pypy' + '.'.join(map(str, sys.version_info[:2])) + '.json'
        result_filename = os.path.join(root_dir, 'sample_results', result_filename)
        result = {}

        for filename in os.listdir(samples_dir):
            full_filename = os.path.join(samples_dir, filename)
            file_result= self.check_filename(full_filename, check_names=True)

            if file_result is not None:
                result[filename] = file_result

        if os.getenv('FIX_EXECUTING_TESTS'):
            with open(result_filename, 'w') as outfile:
                json.dump(result, outfile, indent=4, sort_keys=True)
            return
        else:
            with open(result_filename, "r") as infile:
                old_results = json.load(infile)

            for k, v in old_results.items():
                self.assertEqual(result[k], v, "got different results for %s" % k)

            if any(k not in old_results for k in result):
                if os.getenv("ADD_EXECUTING_TESTS"):
                    with open(result_filename, "w") as outfile:
                        json.dump(result, outfile, indent=4, sort_keys=True)
                    return
                else:
                    self.fail(
                        msg="%s not in old results (set ADD_EXECUTING_TESTS=1 to add them)"
                        % k,
                    )

    def test_module_files(self):
        self.start_time = time.time()
    
        modules = list(sys.modules.values())
        shuffle(modules)
        for module in modules:
            try:
                filename = inspect.getsourcefile(module)
            except TypeError:
                continue
    
            if not filename:
                continue
    
            filename = os.path.abspath(filename)
    
            if (
                    # The sentinel actually appearing in code messes things up
                    'executing' in filename
                    # A file that's particularly slow
                    or 'errorcodes.py' in filename
                    # Contains unreachable code which pypy removes
                    or PYPY and ('sysconfig.py' in filename or 'pyparsing.py' in filename)
            ):
                continue
    
            try:
                self.check_filename(filename, check_names=False)
            except TimeOut:
                print("Time's up")


    def check_filename(self, filename, check_names):
        source = Source.for_filename(filename)

        if source.tree is None:
            # we could not parse this file (maybe wrong python version)
            print("skip %s"%filename)
            return

        if sys.version_info >= (3,11):
            Deadcode.annotate(source.tree)

        print("check %s"%filename)

        if PY3 and sys.version_info < (3, 11):
            code = compile(source.text, filename, "exec", dont_inherit=True)
            for subcode, qualname in find_qualnames(code):
                if not qualname.endswith(">"):
                    code_qualname = source.code_qualname(subcode)
                    self.assertEqual(code_qualname, qualname)

        nodes = defaultdict(list)
        decorators = defaultdict(list)
        expected_decorators = {}
        for node in ast.walk(source.tree):
            if isinstance(node, (
                    (ast.Name,) * check_names,
                    ast.UnaryOp,
                    ast.BinOp,
                    ast.Subscript,
                    ast.Call,
                    ast.Compare,
                    ast.Attribute
            )):
                nodes[node] = []
            elif isinstance(node, (ast.ClassDef, function_node_types)):
                expected_decorators[(node.lineno, node.name)] = node.decorator_list[::-1]
                decorators[(node.lineno, node.name)] = []

        try:
            code = compile(source.tree, source.filename, "exec")
        except SyntaxError:
            # for example:
            # SyntaxError: 'return' outside function
            print("skip %s" % filename)
            return
        result = list(self.check_code(code, nodes, decorators, check_names=check_names))

        if not re.search(r'^\s*if 0(:| and )', source.text, re.MULTILINE):
            for node, values in nodes.items():

                # skip some cases cases 
                if sys.version_info < (3, 11):
                    if is_unary_not(node):
                        continue

                    if sys.version_info >= (3, 8):
                        if is_annotation(node):
                            continue

                    ctx = getattr(node, 'ctx', None)
                    if isinstance(ctx, ast.Store):
                        # Assignment to attributes and subscripts is less magical
                        # but can also fail fairly easily, so we can't guarantee
                        # that every node can be identified with some instruction.
                        continue

                    if isinstance(ctx, (ast.Del, getattr(ast, 'Param', ()))):
                        assert not values, [ast.dump(node), values]
                        continue

                    if isinstance(node, ast.Compare):
                        if sys.version_info >= (3, 10):
                            continue
                        if len(node.ops) > 1:
                            assert not values
                            continue

                        if is_unary_not(node.parent) and isinstance(
                            node.ops[0], (ast.In, ast.Is)
                        ):
                            continue

                    if is_literal(node):
                        continue
                else:
                    # x (is/is not) None
                    none_comparison = (
                        isinstance(node, ast.Compare)
                        and len(node.ops) == 1
                        and isinstance(node.ops[0], (ast.IsNot, ast.Is))
                        and len(node.comparators) == 1
                        and isinstance(node.comparators[0], ast.Constant)
                        and node.comparators[0].value == None
                    )

                    if is_unary_not(node) or none_comparison:
                        # some ast-nodes are transformed into control flow, if it is used at places like `if not a: ...`
                        # There are no bytecode instructions which can be mapped to this ast-node,
                        # because the compiler generates POP_JUMP_FORWARD_IF_TRUE which mapps to the `if` statement.
                        # only code like `a=not b` generates a UNARY_NOT

                        # handles cases like
                        # if not x is None: ...
                        # assert a if cnd else not b

                        first_node = node
                        while is_unary_not(first_node.parent) or (
                            isinstance(first_node.parent, ast.IfExp)
                            and first_node
                            in (first_node.parent.body, first_node.parent.orelse)
                        ):
                            first_node = first_node.parent



                        if isinstance(first_node.parent,(ast.If,ast.Assert,ast.While,ast.IfExp)) and first_node is first_node.parent.test:
                            continue
                        if isinstance(first_node.parent,(ast.match_case)) and first_node is first_node.parent.guard:
                            continue
                        if isinstance(first_node.parent,(ast.BoolOp,ast.Return)):
                            continue
                        if isinstance(first_node.parent,(ast.comprehension)) and first_node in first_node.parent.ifs:
                            continue
                        if isinstance(first_node.parent,(ast.comprehension)) and first_node in first_node.parent.ifs:
                            continue
                        
                    if (
                        isinstance(node, ast.UnaryOp)
                        and isinstance(node.op, ast.Not)
                        and isinstance(node.operand, ast.Compare)
                        and len(node.operand.ops) == 1
                        and isinstance(node.operand.ops[0], (ast.In,ast.Is))
                    ):
                        # `not a in l` the not becomes part of the comparison
                        continue

                    if is_annotation(node):
                        continue

                    if is_literal(node) and not isinstance(node, ast.Constant):
                        continue

                    if isinstance(node,ast.Name) and node.id=="__debug__":
                        continue

                    if isinstance(node, ast.Compare) and len(node.comparators) > 1:
                        continue

                    if is_pattern(node):
                        continue

                    if (
                        isinstance(node, ast.BinOp)
                        and isinstance(node.op, ast.Mod)
                        and isinstance(node.left, ast.Constant)
                        and isinstance(node.right, ast.Tuple)
                        and isinstance(node.left.value, str)
                        and re.fullmatch(r"%(-?\d+)?[sr]", node.left.value)
                    ):
                        # "%50s"%(a,) is missing an BUILD_STRING instruction which normally maps to BinOp
                        continue

                    if getattr(node, "deadcode", False):
                        continue

                    if (
                        isinstance(node, ast.Name)
                        and isinstance(node.ctx, ast.Store)
                        and node.id == "__classcell__"
                    ):
                        continue

                if sys.version_info >= (3, 10):
                    correct = len(values) >= 1
                elif sys.version_info >= (3, 9) and in_finally(node):
                    correct = len(values) > 1
                else:
                    correct = len(values) == 1

                if not correct:

                    def p(*args):
                        print(*args, file=sys.stderr)


                    p("node without associated Bytecode")
                    p("in file:", filename)
                    p("correct:", correct)
                    p("len(values):", len(values))
                    p("values:", values)

                    p()

                    p("ast node:")
                    p(ast_dump(node, indent=4))

                    parents = []
                    parent = node
                    while hasattr(parent, "parent"):
                        parent = parent.parent
                        parents.append(parent)
                    p("parents:", parents)

                    p(
                        "node range:",
                        "lineno=%s" % node.lineno,
                        "end_lineno=%s" % node.end_lineno,
                        "col_offset=%s" % node.col_offset,
                        "end_col_offset=%s" % node.end_col_offset,
                    )

                    dump_source(
                        source.text,
                        start_position(node),
                        end_position(node),
                        file=sys.stderr,
                    )
                    p()

                    p("all bytecodes in this range:")

                    bc = compile(source.text, filename, "exec")

                    def inspect(bc):
                        first = True
                        for i in dis.get_instructions(bc):

                            if (
                                i.positions.lineno is not None
                                and i.positions.lineno <= node.end_lineno
                                and node.lineno <= i.positions.end_lineno
                            ):
                                if first:
                                    p("block name:", bc.co_name)
                                    first = False
                                p(i.positions, i.opname, i.argval)

                        for const in bc.co_consts:
                            if isinstance(const, types.CodeType):
                                inspect(const)

                    inspect(bc)

                    self.fail()

        return result

    def check_code(self, code, nodes, decorators, check_names):
        linestarts = dict(dis.findlinestarts(code))
        instructions = list(get_instructions(code))
        lineno = None
        for inst_index, inst in enumerate(instructions):
            if hasattr(self, "start_time"):
                if time.time() - self.start_time > 45 * 60:
                    # Avoid travis time limit of 50 minutes
                    raise TimeOut

            py11 = sys.version_info >= (3, 11)

            lineno = linestarts.get(inst.offset, lineno)
            if not (
                inst.opname.startswith(
                    (
                        "BINARY_",
                        "UNARY_",
                        "LOAD_ATTR",
                        "LOAD_METHOD",
                        "LOOKUP_METHOD",
                        "SLICE+",
                        "COMPARE_OP",
                        "CALL_",
                        "IS_OP",
                        "CONTAINS_OP",
                        "STORE_SUBSCR",
                        "STORE_ATTR",
                        "STORE_SLICE",
                    )
                    + (
                        "LOAD_NAME",
                        "LOAD_GLOBAL",
                        "LOAD_FAST",
                        "LOAD_DEREF",
                        "LOAD_CLASSDEREF",
                    )
                    * check_names
                )
                or (
                    py11
                    and inst.opname
                    in (
                        "LOAD_GLOBAL",
                        "STORE_ATTR",
                        "DELETE_ATTR",
                        "DELETE_NAME",
                        "DELETE_FAST",
                        "STORE_SUBSCR",
                        "STORE_SLICE",
                        "DELETE_SUBSCR",
                        "STORE_NAME",
                        "STORE_FAST",
                        "STORE_GLOBAL",
                        "STORE_DEREF",
                        "BUILD_STRING",
                        "CALL",
                    )
                )
            ):
                continue

            if py11:
                if (
                    inst.opname == "LOAD_NAME"
                    and hasattr(inst, "positions")
                    and inst.positions.col_offset == inst.positions.end_col_offset == 0
                    and inst.argval == "__name__"
                ):
                    continue

                if (
                    inst.opname == "STORE_NAME"
                    and hasattr(inst, "positions")
                    and inst.positions.col_offset == inst.positions.end_col_offset == 0
                    and inst.argval in ("__module__", "__qualname__")
                ):
                    continue

                if inst.positions.lineno == None:
                    continue

            frame = C()
            frame.f_lasti = inst.offset
            frame.f_code = code
            frame.f_globals = globals()
            frame.f_lineno = lineno
            source = Source.for_frame(frame)
            node = None

            try:
                ex = Source.executing(frame)
                node = ex.node

            except KnownIssue:
                continue

            except VerifierFailure as e:

                print("VerifierFailure:")

                print(e)

                print("\ninstruction: " + str(e.instruction))
                print("\nnode: " + ast.dump(e.node, include_attributes=True))

                with open(source.filename) as sourcefile:
                    source_code = sourcefile.read()

                print(
                    dump_source(
                        source_code, start_position(e.node), end_position(e.node)
                    )
                )

                print("bytecode:")
                for inst in dis.get_instructions(code):
                    if (
                        e.instruction.offset - 10
                        < inst.offset
                        < e.instruction.offset - 10
                    ):
                        print(
                            "%s: %s %s %s"
                            % (
                                inst.offset,
                                inst.positions,
                                inst.opname,
                                inst.argrepr,
                            )
                        )

                self.fail()

            except Exception as e:
                # continue for every case where this can be an known issue


                if py11:
                    exact_options = []
                    for node in ast.walk(source.tree):
                        if not hasattr(node, "lineno"):
                            continue

                        if start_position(node) == start_position(
                            inst
                        ) and end_position(node) == end_position(inst):
                            exact_options.append(node)

                    if inst.opname == "BUILD_STRING":
                        # format strings are still a problem
                        # TODO: find reason
                        continue

                    if any(isinstance(o, ast.JoinedStr) for o in exact_options):
                        # every node in a f-string has the same positions
                        # we are not able to find the correct one
                        continue

                    if (
                        inst.opname == "STORE_FAST"
                        and inst_index > 2
                        and instructions[inst_index - 2].opname == "POP_EXCEPT"
                    ):
                        # except cleanup might be mapped to a method

                        # except Exception as e:
                        #     self.linter._stashed_messages[
                        #         (self.linter.current_name, "useless-option-value")
                        #     ].append((option_string, str(e)))
                        #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        #       | STORE_NAME is mapped to this range
                        #       | and can not be associated with a method, because it is nothing like LOAD_METHOD
                        continue

                    if (
                        inst.opname == "DELETE_FAST"
                        and inst_index > 3
                        and instructions[inst_index - 3].opname == "POP_EXCEPT"
                    ):
                        # same like above
                        continue

                if not py11 and inst.opname.startswith(
                    ("COMPARE_OP", "IS_OP", "CALL", "LOAD_NAME", "STORE_SUBSCR")
                ):
                    continue

                # Attributes which appear ambiguously in modules:
                #   op1.sign, op2.sign = (0, 0)
                #   nm_tpl.__annotations__ = nm_tpl.__new__.__annotations__ = types
                if not py11 and inst.opname == 'STORE_ATTR' and inst.argval in ['sign', '__annotations__']:
                    continue

                if inst.opname == 'LOAD_FAST' and inst.argval == '.0':
                    continue

                if inst.argval == "AssertionError":
                    continue

                if any(
                    isinstance(stmt, (ast.AugAssign, ast.Import))
                    for stmt in source.statements_at_line(lineno)
                ):
                    continue

                # report more information for debugging
                print("mapping failed")

                print(e)
                if isinstance(e, NotOneValueFound):
                    for value in e.values:
                        print(
                            "value:", ast_dump(value, indent=4, include_attributes=True)
                        )

                print("search bytecode", inst)
                print("in file", source.filename)

                if py11:
                    print("at position", inst.positions)

                    with open(source.filename) as sourcefile:
                        source_code = sourcefile.read()

                    dump_source(
                        source_code, start_position(inst), end_position(inst)
                    )

                    options = []
                    for node in ast.walk(ast.parse(source_code)):
                        if not hasattr(node, "lineno"):
                            continue

                        # if {start_position(node), end_position(node)} & {start_position(inst), end_position(inst)}:
                        if start_position(node) <= end_position(
                            inst
                        ) and start_position(inst) <= end_position(node):
                            options.append(node)

                    for node in sorted(
                        options,
                        key=lambda node: (
                            node.end_lineno - node.lineno,
                            node.end_col_offset - node.col_offset,
                        ),
                    ):

                        if (node.end_lineno - node.lineno) > (
                            inst.positions.end_lineno - inst.positions.lineno
                        ) * 4:
                            # skip nodes which are way to long
                            continue

                        print()
                        print(
                            "possible node",
                            node.lineno,
                            node.end_lineno,
                            node.col_offset,
                            node.end_col_offset,
                            ast.dump(node),
                        )

                raise

            if py11 and getattr(node, "deadcode", True) == True:
                print("code is alive:")
                print("There is a bug in the deadcode detection, because the python compiler has generated bytecode for this node.")

                print("deadcode:",getattr(node, "deadcode", "<undefined>"))

                print("node:",ast.dump(node))
                print("line:",node.lineno)

                non_dead_parent=node
                while getattr(non_dead_parent,"deadcode",True)==True:
                    non_dead_parent=non_dead_parent.parent

                dump_source(source.text, start_position(non_dead_parent), end_position(non_dead_parent))

                from deadcode import dump_deadcode

                
                dump_deadcode(non_dead_parent)

                self.fail()

            # `argval` isn't set for all relevant instructions in python 2
            # The relation between `ast.Name` and `argval` is already
            # covered by the verifier and much more complex in python 3.11 
            if isinstance(node, ast.Name) and (PY3 or inst.argval) and not py11:
                self.assertEqual(inst.argval, node.id, msg=(inst, ast.dump(node)))

            if ex.decorator:
                decorators[(node.lineno, node.name)].append(ex.decorator)
            else:
                nodes[node].append((inst, frame.__dict__))

            yield [inst.opname, node_string(source, ex.decorator or node)]

        # do not use code.co_consts because they can contain deadcode https://github.com/python/cpython/issues/96833
        for inst in instructions:
            if isinstance(inst.argval, type(code)):
                for x in self.check_code(inst.argval, nodes, decorators, check_names=check_names):
                    yield x


def node_string(source, node):
    return source.asttokens().get_text(node)


def is_literal(node):
    if isinstance(node, ast.UnaryOp):
        return is_literal(node.operand)

    if isinstance(node, ast.BinOp):
        return is_literal(node.left) and is_literal(node.right)

    if isinstance(node, ast.Compare):
        return all(map(is_literal, [node.left] + node.comparators))

    if isinstance(node, ast.Subscript) and is_literal(node.value):
        if isinstance(node.slice, ast.Slice):
            return all(
                x is None or is_literal(x)
                for x in [
                    node.slice.lower,
                    node.slice.upper,
                    node.slice.step,
                ]
            )
        else:
            return is_literal(subscript_item(node))

    if isinstance(node,ast.Tuple):
        # pub_fields=(b"x" * 32,) * 2,
        # generates on const element in the bytecode
        return all(is_literal(e) for e in node.elts)

    try:
        ast.literal_eval(node)
        return True
    except ValueError:
        return False


def is_pattern(node):
    while not isinstance(node, ast.pattern):
        if hasattr(node, "parent"):
            node = node.parent
        else:
            return False
    return True

class C(object):
    @staticmethod
    def f():
        pass

    class D(object):
        @staticmethod
        def g():
            pass

        @staticmethod
        def h():
            def i():
                def j():
                    pass

                return j

            return i()


def f():
    def g():
        pass

    return g


# TestFiles().test_files()


def lambda_maker():
    def assign(x):
        def decorator(func):
            func.x = x
            return func

        return decorator

    @assign(lambda: 1)
    def foo():
        return lambda: lambda: 3

    return foo


lamb = lambda: 0


assert tester([1, 2, 3]) == [1, 2, 3]

assert tester.asd is tester
assert tester[1 + 2] is tester
assert tester ** 4 is tester
assert tester * 3 is tester
assert tester - 2 is tester
assert tester + 1 is tester
assert -tester is +tester is ~tester is tester
assert (tester < 7) is tester
assert (tester >= 78) is tester
assert (tester != 79) is tester
# assert (5 != tester != 6) is tester
assert tester.foo(45, False) == 45

assert (tester or 234) == 234
assert (tester and 1123) is tester


def empty_decorator(func):
    return func


def decorator_with_args(*_, **__):
    return empty_decorator


def find_qualnames(code, prefix=""):
    for subcode in code.co_consts:
        if type(subcode) != type(code):
            continue
        qualname = prefix + subcode.co_name
        instructions = list(get_instructions(subcode))[:4]
        opnames = [inst.opname for inst in instructions]
        arg_reprs = [inst.argrepr for inst in instructions]
        is_class = (
            opnames == "LOAD_NAME STORE_NAME LOAD_CONST STORE_NAME".split()
            and arg_reprs == ["__name__", "__module__", repr(qualname), "__qualname__"]
        )
        yield subcode, qualname
        for x in find_qualnames(
            subcode, qualname + ("." if is_class else ".<locals>.")
        ):
            yield x


if __name__ == '__main__':
    unittest.main()

