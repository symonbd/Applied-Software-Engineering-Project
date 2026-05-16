import os
import shutil
from collections import defaultdict


class ProjectReconstructor:

    def __init__(self, base_dir):

        self.base_dir = base_dir

    def reconstruct(self):

        grouped_files = defaultdict(list)

        for repo in os.listdir(self.base_dir):

            repo_path = os.path.join(self.base_dir, repo)

            if not os.path.isdir(repo_path):
                continue

            for project_folder in os.listdir(repo_path):

                folder_path = os.path.join(repo_path, project_folder)

                if not os.path.isdir(folder_path):
                    continue

                for file in os.listdir(folder_path):

                    base = file.split(".")[0]

                    grouped_files[base].append(
                        os.path.join(folder_path, file)
                    )

        self._rebuild(grouped_files)

    def _rebuild(self, grouped_files):

        for project_name, files in grouped_files.items():

            if len(files) < 2:
                continue

            target_dir = os.path.join(
                self.base_dir,
                "reconstructed_projects",
                project_name
            )

            os.makedirs(target_dir, exist_ok=True)

            for f in files:

                try:

                    filename = os.path.basename(f)

                    new_path = os.path.join(target_dir, filename)

                    if not os.path.exists(new_path):
                        shutil.copy(f, new_path)

                except Exception as e:

                    print("Reconstruction error:", e)