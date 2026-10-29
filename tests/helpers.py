import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "skills", "scout", "scripts")
sys.path.insert(0, SCRIPTS)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def make_skill(root, name, description, extra=""):
    write(os.path.join(root, name, "SKILL.md"),
          f"---\nname: {name}\ndescription: {description}\n{extra}---\n\nBody of {name}.\n")
    return os.path.join(root, name)
