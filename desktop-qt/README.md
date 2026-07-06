# gui4gmns / desktop-qt — Qt desktop viewer (v1: PySide6; C++ port follows same design)
`nexta_qt.py` — QMainWindow with the classic NEXTA structure: Layer Control Panel dock, MOE toolbar,
Animation View (time slider + play), inspector, summary statistics, engine-log dock.
Unique to this branch: **Run engine** (QProcess -> dlsim_run.exe on the open folder, log tail, auto
reload) and live-follow polling. Headless CI mode: `--snapshot out.png [--moe td] [--time 07:30]`.
Verified 2026-07-02 (offscreen renders in `snapshots/`): Chicago Sketch (TD 07:30 + vehicles),
Chicago Regional (39k links), **ARC Atlanta 145,971 links**, toy merge. Requires `pip install PySide6`.
C++/Qt port: keep widget & data design 1:1; move canvas to QOpenGLWidget for animation at ARC scale.
