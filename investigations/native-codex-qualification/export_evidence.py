import pathlib,shutil,sys,stat
root=pathlib.Path(sys.argv[1]);source=root/'evidence';paths=list(source.rglob('*'))
assert len(paths)<1024
assert all(not p.is_symlink() and (p.is_dir() or stat.S_ISREG(p.lstat().st_mode)) for p in paths)
assert sum(p.stat().st_size for p in paths if p.is_file())<16*1024*1024
shutil.copytree(source,root/'public-evidence')
