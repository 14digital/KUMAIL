from pathlib import Path


def test_downloadable_updater_contains_the_reviewed_powershell_source():
    root=Path(__file__).parents[2]
    launcher=(root/'Update My Intelligence.cmd').read_text()
    header,separator,source=launcher.rpartition('# BEGIN POWERSHELL\n')
    assert separator
    assert source==(root/'scripts/update-windows.ps1').read_text()
    assert 'MI_UPDATER_ROOT=%~dp0' in header
    assert 'exit /b 0' in header
