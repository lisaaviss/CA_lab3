"""
Unit-тесты для процессора
"""
import unittest
import processor


class ProcessorTest(unittest.TestCase):
    """
    Unit-тесты для процессора
    """
    input = "tests/input.json"

    def start_machine(self, output, output_type='str'):
        return processor.launch_processor([output, self.input, output_type])

    def test_cat(self):
        output = self.start_machine("tests/cat")[0]
        self.assertEqual(output, 'hello world')

    def test_hello(self):
        output = self.start_machine("tests/hello")[0]
        self.assertEqual(output, 'hello world')

    def test_prob1(self):
        output = self.start_machine("tests/prob2", "int")[0]
        self.assertEqual(output, '4613732')

    def test_var(self):
        output = self.start_machine("tests/var_test")[0]
        self.assertEqual(output, 'test')
