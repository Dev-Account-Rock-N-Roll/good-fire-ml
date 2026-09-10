import io
import unittest

from lib_good_fire_ml.landis.landis_input import (
    UNIVERSAL_SEED_DISTANCE,
    PostFireRegeneration,
    parse_ecoregions,
    parse_scenario,
    parse_species,
)


class TestLandisParsing(unittest.TestCase):
    def test_scenario_parser_valid(self):
        scenario_text = """
        LandisData Scenario
        
        Duration  300
        Species   ./species.txt
        Ecoregions      "./ecoregions.txt"
        EcoregionsMap   "./ecoregions.img"
        CellLength      25.0
        RandomNumberSeed 4357
        
        >> Plug-in                  Initialization File
        "Age-only succession"    succession.txt
        Age-only.Wind            "age only/wind.txt"
        """
        scenario = parse_scenario(io.StringIO(scenario_text))

        self.assertEqual(scenario.duration, 300)
        self.assertEqual(scenario.species_filepath, "./species.txt")
        self.assertEqual(scenario.cell_length, 25.0)
        self.assertEqual(scenario.random_number_seed, 4357)
        self.assertEqual(len(scenario.extensions), 2)
        self.assertEqual(scenario.extensions[0].name, "Age-only succession")
        self.assertEqual(scenario.extensions[1].initialization_file, "age only/wind.txt")

    def test_species_parser_valid(self):
        species_text = """
        LandisData Species
        
        >> Name   Longevity Maturity Shade Fire Eff Max VegRep Min Max Regen
        abiebals    200        25       5     1    130 160 0.0     0   0   none
        acerrubr    150        10       4     1    uni 200 0.5     0 100   resprout
        """
        species_list = parse_species(io.StringIO(species_text))

        self.assertEqual(len(species_list), 2)

        abie = species_list[0]
        self.assertEqual(abie.name, "abiebals")
        self.assertEqual(abie.longevity, 200)
        self.assertEqual(abie.post_fire_regeneration, PostFireRegeneration.NONE)

        acer = species_list[1]
        self.assertEqual(acer.effective_seed_distance, UNIVERSAL_SEED_DISTANCE)
        self.assertEqual(acer.post_fire_regeneration, PostFireRegeneration.RESPROUT)

    def test_species_parser_invalid_longevity(self):
        species_text = """
        LandisData Species
        abiebals    -200        25       5     1    130 160 0.0     0   0   none
        """
        with self.assertRaisesRegex(ValueError, "Longevity must be >= 0"):
            parse_species(io.StringIO(species_text))

    def test_species_parser_invalid_maturity(self):
        species_text = """
        LandisData Species
        abiebals    200        250       5     1    130 160 0.0     0   0   none
        """
        with self.assertRaisesRegex(ValueError, "Maturity.*must be >= 0 and <= longevity"):
            parse_species(io.StringIO(species_text))

    def test_ecoregions_parser_valid(self):
        ecoregion_text = """
        LandisData Ecoregions
        
        >> Active Code Name  Description
        yes       99   SE-pb "SE pine barrens"
        no        1    water water
        """
        eco_list = parse_ecoregions(io.StringIO(ecoregion_text))
        self.assertEqual(len(eco_list), 2)

        se_pb = eco_list[0]
        self.assertTrue(se_pb.active)
        self.assertEqual(se_pb.map_code, 99)
        self.assertEqual(se_pb.name, "SE-pb")
        self.assertEqual(se_pb.description, "SE pine barrens")

    def test_ecoregions_parser_duplicate_map_code(self):
        ecoregion_text = """
        LandisData Ecoregions
        yes       99   SE-pb "SE pine barrens"
        no        99   water water
        """
        with self.assertRaisesRegex(ValueError, "Map code 99 is repeated."):
            parse_ecoregions(io.StringIO(ecoregion_text))


if __name__ == "__main__":
    unittest.main()
