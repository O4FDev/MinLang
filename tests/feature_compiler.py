def accepts_managed_graph(test, source):
    result, llvm = test.compile(source)
    test.assertEqual(result.returncode, 0, result.stderr)
    test.assertTrue(llvm.exists())
    test.assertIn('; minyar-cycle-runtime: 1\n', llvm.read_text())
    return llvm
