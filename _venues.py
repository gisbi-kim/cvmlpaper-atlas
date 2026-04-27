"""Single source of truth for venue config.
Import this from _make_all_html.py, _make_coauthor_network.py, etc.
"""

# CV cluster: blues/teals   ML cluster: reds/oranges
VENUES_CFG = [
    {'label': 'CVPR',    'id': 'cvpr',    'color': '#1f77b4', 'since': 1983, 'cluster': 'CV'},
    {'label': 'ICCV',    'id': 'iccv',    'color': '#4da6e8', 'since': 1987, 'cluster': 'CV'},
    {'label': 'ECCV',    'id': 'eccv',    'color': '#2ca02c', 'since': 1990, 'cluster': 'CV'},
    {'label': '3DV',     'id': '3dv',     'color': '#17becf', 'since': 1999, 'cluster': 'CV'},
    {'label': 'NeurIPS', 'id': 'neurips', 'color': '#d62728', 'since': 1987, 'cluster': 'ML'},
    {'label': 'ICML',    'id': 'icml',    'color': '#ff7f0e', 'since': 1980, 'cluster': 'ML'},
    {'label': 'ICLR',    'id': 'iclr',    'color': '#e87c2f', 'since': 2013, 'cluster': 'ML'},
]

CV_VENUES  = {v['label'] for v in VENUES_CFG if v['cluster'] == 'CV'}
ML_VENUES  = {v['label'] for v in VENUES_CFG if v['cluster'] == 'ML'}

# Node colors for co-author network clustering
CLUSTER_COLORS = {
    'CV':    '#1f77b4',   # blue
    'ML':    '#d62728',   # red
    'Mixed': '#9467bd',   # purple
}

VENUE_LABELS   = [v['label'] for v in VENUES_CFG]
VENUE_PRIORITY = {v['label']: i for i, v in enumerate(VENUES_CFG)}
VENUE_COLORS   = {v['label']: v['color'] for v in VENUES_CFG}
VENUE_IDS      = {v['label']: v['id'] for v in VENUES_CFG}
VENUE_CLUSTERS = {v['label']: v['cluster'] for v in VENUES_CFG}
