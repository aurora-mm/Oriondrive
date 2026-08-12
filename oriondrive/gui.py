from __future__ import annotations
from .ui.state import FIELD_GROUPS, ROLE_OPTIONS, default_project_filename, gui_state_to_project, preset_project, project_to_gui_state, project_to_section_dicts

def main() -> None:
    try:
        from .ui.macapp import main as run_app
    except ImportError as exc:
        raise RuntimeError('The Oriondrive desktop app needs PyObjC on macOS. Install dependencies with `python -m pip install -r requirements.txt`.') from exc
    run_app()
if __name__ == '__main__':
    main()
