import os

def _get_project_root():
    """
    Returns the root directory of the project.
    """
    current_path = os.path.abspath(__file__)
    dir_path = os.path.dirname(current_path)

    # Define common marker files/directories
    marker_files = [
        "pyproject.toml", ".git", "setup.py", "requirements.txt", "LICENSE"
    ]

    while dir_path != os.path.dirname(dir_path):
        for marker in marker_files:
            if os.path.exists(os.path.join(dir_path, marker)):
                return dir_path
        dir_path = os.path.dirname(dir_path)
    return None


print(_get_project_root())