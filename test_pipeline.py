def test_project_imports():
    import app.pipeline
    import app.metrics
    assert app.pipeline.RelayPipeline
