pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

configure_file(
  input: 'texmanager.in',
  output: 'texmanager',
  configuration: configuration_data({'PKGDATADIR': pkgdatadir}),
  install_dir: get_option('bindir'),
)

desktop_conf = configuration_data()
desktop_conf.set('PKGDATADIR', pkgdatadir)
configure_file(
  input: 'texmanager.desktop.in',
  output: 'org.example.TexManager.desktop',
  configuration: desktop_conf,
  install_dir: join_paths(get_option('datadir'), 'applications'),
)
