test_parameters = {
    "svs": {
        "CMU-1/CMU-1.svs": {
            "convert": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 25.691574, "y": 23.449873},
            "read_region": [
                {
                    "location": {"x": 900, "y": 1200},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "ee6fc53c821ed39eb8bb9ea31d6065eb",
                },
                {
                    "location": {"x": 450, "y": 600},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "90d96fafc102df44225b6073e6cd4e3b",
                },
                {
                    "location": {"x": 225, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "2225853ad4952b9f1854f9cb97c6736b",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 16400, "y": 21200},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                }
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "b27df8f554f6bdd4d4fa42d67eeebe6e",
                }
            ],
        },
        "svs1/input.svs": {
            "convert": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 18.34152, "y": 22.716894},
            "read_region": [
                {
                    "location": {"x": 500, "y": 500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "b5dae0fce9692bdbb1ab2799d7874402",
                },
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "b08559b881da13a6c0fb218c44244951",
                },
                {
                    "location": {"x": 100, "y": 100},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 8000, "y": 8000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "379210d2aee83bb590aa2a4223707ac1",
                }
            ],
        },
    },
    "czi": {
        "czi1/input.czi": {
            "convert": False,
            "include_levels": [0],
            "lowest_included_pyramid_level": 0,
            "tile_size": 512,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 30000, "y": 30000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "aa9e76930398facc8c7910e053a7f418",
                }
            ],
            "read_region_openslide": [],
            "read_thumbnail": [],
        }
    },
    "mirax": {
        "CMU-1/CMU-1.mrxs": {
            "convert": True,
            "include_levels": [4, 6],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "encode_format": "jpeg2000",
            "encode_quality": 0,
            "photometric_interpretation": "YBR_ICT",
            "image_coordinate_system": {"x": 2.3061675, "y": 20.79015},
            "read_region": [
                # OpenSlide produces different results across platforms
                # {
                #     "location": {
                #         "x": 50,
                #         "y": 100
                #     },
                #     "level": 6,
                #     "size": {
                #         "width": 500,
                #         "height": 500
                #     },
                #     "md5": "fe29e76f5904d65253d8eb742b244789"
                # },
                # {
                #     "location": {
                #         "x": 400,
                #         "y": 500
                #     },
                #     "level": 4,
                #     "size": {
                #         "width": 500,
                #         "height": 500
                #     },
                #     "md5": "4f4c904ed9257e385fc8f0818337d9e7"
                # }
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 50, "y": 100},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                },
                {
                    "location": {"x": 400, "y": 500},
                    "level": 4,
                    "size": {"width": 500, "height": 500},
                },
            ],
            "read_thumbnail": [],
        }
    },
    "ndpi": {
        "CMU-1/CMU-1.ndpi": {
            "convert": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 940, "y": 1500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "d0c6f57e80b8a05e5617049d1e880425",
                },
                {
                    "location": {"x": 470, "y": 750},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "705072936f3171e04d22e82a36340250",
                },
                {
                    "location": {"x": 235, "y": 375},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "29949c1bbf444113b8f07d0ba454b25e",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 940, "y": 1500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 235, "y": 375},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "ea87500dc544f45c6f600811138dad23",
                }
            ],
        },
        "ndpi1/input.ndpi": {
            "convert": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 0, "y": 0},
                    "level": 8,
                    "size": {"width": 200, "height": 200},
                    "md5": "3053d9c4e6fe5b77ce1ac72788e1c5ee",
                },
                {
                    "location": {"x": 100, "y": 100},
                    "level": 8,
                    "size": {"width": 200, "height": 200},
                    "md5": "a435e9806ba8a9a8227ebbb99728235c",
                },
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "md5": "15f166e1facb38aba2eb47f7622c5c3c",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                }
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "995791915459762ac1c251fc8351b4f6",
                }
            ],
        },
        # "ndpi2/input.ndpi": {
        #     "convert": True,
        #     "include_levels": [4, 6],
        #     "lowest_included_pyramid_level": 4,
        #     "tile_size": 1024,
        #     "photometric_interpretation": "YBR_FULL_422",
        #     "image_coordinate_system": {
        #         "x": 0.0,
        #         "y": 0.0
        #     },
        #     "read_region": [
        #         {
        #             "location": {
        #                 "x": 3000,
        #                 "y": 3000
        #             },
        #             "level": 4,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #             "md5": "fee89f955ed08550391b59cdff4a7aef"
        #         },
        #         {
        #             "location": {
        #                 "x": 1000,
        #                 "y": 1000
        #             },
        #             "level": 6,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #             "md5": "59afbe85473f23038e97ee40213862b4"
        #         }
        #     ],
        #     "read_region_openslide": [
        #         {
        #             "location": {
        #                 "x": 3000,
        #                 "y": 3000
        #             },
        #             "level": 4,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #         },
        #         {
        #             "location": {
        #                 "x": 1000,
        #                 "y": 1000
        #             },
        #             "level": 6,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #         }
        #     ],
        #     "read_thumbnail": [
        #         {
        #             "size": {
        #                 "width": 512,
        #                 "height": 512
        #             },
        #             "md5": "701961c4afcf42d545e30ad8346fc8f4"
        #         }
        #     ]
        # }
    },
    "philips_tiff": {
        "philips1/input.tif": {
            "convert": True,
            "include_levels": [4, 5, 6],
            "lowest_included_pyramid_level": 4,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 500, "y": 1000},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "38d562c38a21c503dd1da6faff8ac129",
                },
                {
                    "location": {"x": 150, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "faa48eb511e39271dd222a89ef853c76",
                },
                {
                    "location": {"x": 1000, "y": 2000},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "b35b1013f4009ce11f29b82a52444191",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 500, "y": 1000},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 150, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 1000, "y": 2000},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "922ab1407d79de6b117bc561625f1a49",
                }
            ],
        }
    },
}
