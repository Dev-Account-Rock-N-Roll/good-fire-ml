import ntpath
from pathlib import Path

import chardet


class LandisConfigurationFile:
    def __init__(self, path: Path, file_path: str):
        self.path = path
        self.file_name = ntpath.basename(file_path)
        self.related_input_files = set()
        self.config = self._get_keys_from_configuration_file(self.file_name)

    def _check_original_folder_and_remove_path_prefix_from_value(self, value) -> object:
        """Removes any path prefix from a value, returning only the file name."""
        if isinstance(value, str) and self.file_path_is_from_original_input_folder(value):
            file_name = ntpath.basename(value)
            self.related_input_files.add(file_name)
            return file_name
        else:
            return value

    def _get_keys_from_configuration_file(self, configuration_file: str) -> dict[str, object]:
        """Extracts Key-Value pairs from the chaotic text format."""
        data = {}
        target_file = self.path / configuration_file
        if target_file:
            with open(target_file, "rb") as f:
                file_content = f.read()
                file_encoding = chardet.detect(file_content)["encoding"]
                print(f"Reading configuration from: {target_file}. File encoding: {file_encoding}")
                decoded_content = file_content.decode(file_encoding)
                non_comment_lines = [
                    line
                    for line in decoded_content.splitlines()
                    if not line.strip().startswith(">>")
                ]
                key_value_pairs = [
                    self._get_key_and_value_from_line(line) for line in non_comment_lines
                ]
                data = {
                    k: self._format_config_value(v)
                    for k, v in key_value_pairs
                    if k != None and v != None
                }
        return data

    def _get_key_and_value_from_line(self, line) -> tuple[str, str]:
        if line.startswith(">>"):
            return None, None
        if line.startswith(("'", '"')):
            split_text = line.split(line[0])
            return split_text[1], "".join(split_text[2:])
        split_text = line.split(None, 1)
        if split_text and len(split_text) == 2:
            return split_text[0], split_text[1]
        return None, None

    def _format_config_value(self, value) -> object:
        if isinstance(value, str):
            formatted_value = value.strip()
            formatted_value = self._remove_end_of_line_comments_from_value(formatted_value)
            formatted_value = self._check_original_folder_and_remove_path_prefix_from_value(
                formatted_value
            )
            return formatted_value
        return value

    def _remove_end_of_line_comments_from_value(self, value):
        """Removes any end-of-line comment from a value, returning only the relevant part."""
        if isinstance(value, str):
            return value.split("<<")[0].strip()
        return value

    @staticmethod
    def file_path_is_from_original_input_folder(file_path):
        input_folder_path_prefix = "G:\\Remy\\LANDISruns\\common\\"
        return file_path.startswith(input_folder_path_prefix)
