import os

dirs = [
    "app",
    "app/services",
    "app/ingestion",
    "app/graph",
]

files = [
    "app/__init__.py",
    "app/main.py",
    "app/config.py",
    "app/state.py",
    "app/services/__init__.py",
    "app/services/fireflies.py",
    "app/services/storage.py",
    "app/ingestion/__init__.py",
    "app/ingestion/webhook.py",
    "app/graph/__init__.py",
    "app/graph/nodes.py",
    "app/graph/workflow.py",
]

for d in dirs:
    os.makedirs(d, exist_ok=True)

for f in files:
    with open(f, 'w') as fp:
        pass

print("Structure created.")
