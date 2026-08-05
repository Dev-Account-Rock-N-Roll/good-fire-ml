from pathlib import Path

import rasterio

from .landis_configuration import LandisConfigurationFile


class LandisRun:
    def __init__(self, run_directory, scenario_file="scenario.txt"):
        self.path = Path(run_directory)
        # 1. Parse Text Inputs (Lazy Load)
        self.root_config = LandisConfigurationFile(self.path, scenario_file)
        self.input_file_container = self._load_full_scenario_configuration(self.root_config)

    def _load_full_scenario_configuration(
        self, scenario_file: LandisConfigurationFile
    ) -> dict[str, LandisConfigurationFile]:
        """Combines scenario file and other configuration files into a single dictionary."""
        input_file_dictionary = {scenario_file.file_name: scenario_file}
        # Parse initial config recursively to handle nested config files
        full_input_file_dictionary = self._recursive_parse(scenario_file, input_file_dictionary)
        return full_input_file_dictionary

    def _recursive_parse(
        self, scenario_file: LandisConfigurationFile, input_file_dictionary: dict, layer=0
    ):
        """Recursively parses configuration dictionary to handle nested config files."""
        print(f"Parsing layer {layer} with related files: {scenario_file.related_input_files}")
        for input_file in scenario_file.related_input_files:
            if input_file.endswith(".txt") and input_file not in input_file_dictionary:
                nested_config = LandisConfigurationFile(self.path, input_file)
                input_file_dictionary[input_file] = nested_config
                self._recursive_parse(nested_config, input_file_dictionary, layer=layer + 1)
        return input_file_dictionary

    def get_input_tensor(self, filename="initial_communities.img"):
        """Returns input landscape as a 3D NumPy array (Channels, H, W)."""
        file_path = self.path / filename
        with rasterio.open(file_path) as src:
            return src.read()  # Shape: (Bands, Height, Width)

    def get_output_label(self, filename="biomass-succession-log.tif"):
        """Returns simulation target as a 3D NumPy array."""
        file_path = self.path / filename
        with rasterio.open(file_path) as src:
            return src.read()

    def __repr__(self):
        return f"<LandisRun: {self.path.name} | Config Keys: {list(self.config.keys())}>"
