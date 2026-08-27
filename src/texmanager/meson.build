gnome = import('gnome')
python = import('python').find_installation('python3')

pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
pythondir = python.get_install_dir()

install_data(
  [
    '__init__.py',
    'application.py',
    'window.py',
    'dialogs.py',
    'models.py',
  ],
  install_dir: join_paths(pythondir, 'texmanager'),
)
