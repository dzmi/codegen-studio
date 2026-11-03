# -*- coding: utf-8 -*-
"""Git через dulwich (чистый Python), fallback на subprocess git."""
import os
import subprocess

try:
    from dulwich import porcelain
    from dulwich.repo import Repo
    HAS_DULWICH = True
except ImportError:
    HAS_DULWICH = False


def _has_subprocess_git():
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


class GitPy:
    def __init__(self, project_path):
        self.project_path = project_path
        self.has_subprocess = _has_subprocess_git()

    def is_repo(self):
        return os.path.isdir(os.path.join(self.project_path, ".git"))

    def available(self):
        return HAS_DULWICH or self.has_subprocess

    def backend(self):
        if HAS_DULWICH:
            return "dulwich"
        if self.has_subprocess:
            return "subprocess git"
        return "none"

    def init(self):
        if self.is_repo():
            return False, "Уже инициализирован"
        if HAS_DULWICH:
            try:
                porcelain.init(self.project_path)
                return True, ""
            except Exception:
                pass
        if self.has_subprocess:
            try:
                subprocess.run(["git", "init"], cwd=self.project_path, check=True, capture_output=True)
                return True, ""
            except Exception as e:
                return False, str(e)
        return False, "Git недоступен"

    def status(self):
        if not self.is_repo():
            return "Не git-репозиторий"
        if self.has_subprocess:
            try:
                r = subprocess.run(["git", "status", "--short"], cwd=self.project_path,
                                   capture_output=True, text=True, timeout=10)
                return r.stdout.strip() or "Чисто"
            except Exception as e:
                return f"Ошибка: {e}"
        if HAS_DULWICH:
            try:
                st = porcelain.status(Repo(self.project_path))
                lines = []
                for p in st.unstaged:
                    lines.append(f"M: {p.decode() if isinstance(p, bytes) else p}")
                for p in st.staged:
                    lines.append(f"A: {p.decode() if isinstance(p, bytes) else p}")
                for p in st.untracked:
                    lines.append(f"?: {p.decode() if isinstance(p, bytes) else p}")
                return "\n".join(lines) or "Чисто"
            except Exception as e:
                return f"Ошибка: {e}"
        return "Git недоступен"

    def log(self, limit=20):
        if not self.is_repo() or not self.has_subprocess:
            return []
        try:
            r = subprocess.run(
                ["git", "log", f"-n{limit}", "--pretty=format:%h|%ci|%s"],
                cwd=self.project_path, capture_output=True, text=True, timeout=10,
            )
            out = []
            for line in r.stdout.splitlines():
                parts = line.split("|", 2)
                if len(parts) == 3:
                    out.append({"hash": parts[0], "date": parts[1], "message": parts[2]})
            return out
        except Exception:
            return []

    def commit(self, message):
        if not self.is_repo():
            return False, "Не git-репозиторий"
        if self.has_subprocess:
            try:
                subprocess.run(["git", "add", "."], cwd=self.project_path, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", message], cwd=self.project_path, check=True, capture_output=True)
                return True, ""
            except subprocess.CalledProcessError as e:
                err = (e.stderr or b"").decode(errors="ignore")
                if "nothing to commit" in err:
                    return False, "Нет изменений для коммита"
                return False, err or str(e)
        return False, "Git недоступен"
