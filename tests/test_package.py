def test_package_is_importable():
    import matrixlang

    assert isinstance(matrixlang.__version__, str)
