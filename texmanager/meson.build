python = import('python').find_installation('python3')
pythondir = python.get_install_dir()

install_data(
  [
    '__init__.py',
    'application.py',
    'window.py',
    'dialogs.py',
    'models.py',
    'detection.py',
  ],
  install_dir: join_paths(pythondir, 'texmanager'),
)
