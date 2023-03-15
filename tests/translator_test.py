"""
Unit-тесты для транслятора
"""

import unittest

import translation

import isa


class TranslatorTest(unittest.TestCase):
    """Unit-тесты для транслятора"""

    def simple_test(self, input_file, output, correct):
        translation.main([input_file, output])

        result_code = isa.read_code(output)
        correct_code = isa.read_code(correct)

        self.assertEqual(result_code, correct_code)

    def test_cat(self):
        self.simple_test("tests/cat.asm", "tests/cat.test", "tests/cat")

    def test_prob2(self):
        self.simple_test("tests/prob2.asm", "tests/prob2.test", "tests/prob2")

    def test_hello_world(self):
        self.simple_test("tests/hello.asm", "tests/hello.test", "tests/hello")

    def test_var(self):
        self.simple_test("tests/var_test.asm", "tests/var_test.test", "tests/var_test")
