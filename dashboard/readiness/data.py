"""Explicit source loading. Missing real/team files never become sample data silently."""
from pathlib import Path
from .contracts import FILES, ContractError, load_bundle

TEAM_PATHS = {
    'manifest.json': ('parking','manifest.json'),
    'baseline.csv': ('sources','baseline.csv'),
    'assumptions.csv': ('sources','assumptions.csv'),
    'demand_predictions.csv': ('forecast','demand_predictions.csv'),
    'uncertainty_results.csv': ('forecast','uncertainty_results.csv'),
    'resource_requirements.csv': ('parking','resource_requirements.csv'),
    'scenario_recommendations.json': ('parking','scenario_recommendations.json'),
}

def read_paths(paths):
    missing=[name for name,path in paths.items() if not path.is_file()]
    if missing: raise ContractError('Missing inputs: '+', '.join(missing))
    files={}
    for name,path in paths.items():
        if path.stat().st_size>2_000_000: raise ContractError(f'{name} exceeds 2 MB.')
        try: files[name]=path.read_text(encoding='utf-8-sig')
        except UnicodeError: raise ContractError(f'{name} must be UTF-8 text.')
    return files

def sample_bundle(app_root):
    return load_bundle(read_paths({n:Path(app_root)/'sample-data'/n for n in FILES}))

def team_paths(repo_root):
    return {n:Path(repo_root).joinpath(*parts) for n,parts in TEAM_PATHS.items()}

def team_status(repo_root):
    return [{'file':n,'path':'/'.join(TEAM_PATHS[n]),'present':p.is_file()} for n,p in team_paths(repo_root).items()]

def team_bundle(repo_root):
    return load_bundle(read_paths(team_paths(repo_root)))


def native_paths(repo_root):
    from .team_adapter import NATIVE_PATHS
    from .parking_variants import EXTENSION_PATHS
    paths={k:Path(repo_root)/v for k,v in NATIVE_PATHS.items()}
    extensions={k:Path(repo_root)/v for k,v in EXTENSION_PATHS.items()}
    if any(p.exists() for p in extensions.values()):
        paths.update(extensions)  # Partial releases fail in read_paths, never silently fall back.
    return paths


def native_bundle(repo_root):
    from .team_adapter import load_native
    from .release_status import attach_release_status
    paths=native_paths(repo_root)
    raw=read_paths(paths)
    bundle=attach_release_status(repo_root,load_native(raw))
    if raw!=read_paths(paths):
        raise ContractError('Inputs changed during loading; retry with a complete, stable release.')
    return bundle


def native_status(repo_root):
    from .team_adapter import NATIVE_PATHS
    from .parking_variants import EXTENSION_PATHS
    return [{'file':k,'path':v,'present':(Path(repo_root)/v).is_file()} for k,v in (NATIVE_PATHS|EXTENSION_PATHS).items()]
