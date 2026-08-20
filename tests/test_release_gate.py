from digital_paint.core.release_gate import v100_release_gate


def test_v100_gate_fails_without_external_verification():
    report = v100_release_gate(
        exe_exists=False,
        offline_launch_verified=False,
        real_sample_regression_passed=False,
        vector_pdf_verified=True,
        qc_passed=True,
        gui_nonblocking_verified=True,
        large_image_benchmarks_passed=False,
        palette_verified=True,
    )
    assert report.passed is False
    assert "V100: FAIL" in report.summary()


def test_v100_gate_passes_only_when_every_requirement_is_true():
    report = v100_release_gate(
        exe_exists=True,
        offline_launch_verified=True,
        real_sample_regression_passed=True,
        vector_pdf_verified=True,
        qc_passed=True,
        gui_nonblocking_verified=True,
        large_image_benchmarks_passed=True,
        palette_verified=True,
    )
    assert report.passed is True
