"""
One-shot script to add a 'transistors' column to trash2.csv.
Maps each entry to a transistor count based on researched data.
For DATACENTER/ARRAY entries, transistors = 0 (not applicable).
"""
import csv, os, re

# ── transistor lookup ────────────────────────────────────────────────
# Keys are (name_fragment, category, year) or just name_fragment.
# We match by checking if the CSV 'name' contains the fragment (case-insensitive).
# More specific matches are tried first.

# Helper: build a dict keyed on exact CSV row name -> transistor count.
# We'll populate this massive dict from the research results.

TRANSISTORS = {
    # ================================================================
    # NVIDIA CLASSIC GPUs
    # ================================================================
    "NV1": 1_000_000,
    "STG2000": 1_000_000,
    "GeForce2 MX 400": 20_000_000,
    "GeForce2 GTS": 25_000_000,
    "GeForce3 Ti 200": 57_000_000,
    "GeForce3 Ti 500": 57_000_000,
    "GeForce4 MX 440": 27_000_000,
    "GeForce4 MX 4000": 27_000_000,
    "GeForce4 Ti 4200": 63_000_000,
    "GeForce4 Ti 4600": 63_000_000,
    "GeForce FX 5200 64-bit": 47_000_000,
    "GeForce FX 5200 128-bit": 47_000_000,
    "GeForce FX 5200 \u2018Leaky Cap": 47_000_000,
    "GeForce FX 5200": 47_000_000,
    "GeForce FX 5500": 47_000_000,
    "GeForce FX 5600 (non-Ultra)": 80_000_000,
    "GeForce FX 5600 Ultra": 80_000_000,
    "GeForce FX 5700 LE": 82_000_000,
    "GeForce FX 5700VE": 82_000_000,
    "GeForce FX 5800 Ultra": 125_000_000,
    "GeForce FX 5800": 125_000_000,
    "GeForce FX 5900 Ultra": 130_000_000,
    "GeForce 6100 IGP": 30_000_000,
    "GeForce 6150 LE": 30_000_000,
    "GeForce 6200 TurboCache": 77_000_000,
    "GeForce 6200 SE TurboCache": 77_000_000,
    "GeForce 6200 TC": 77_000_000,
    "GeForce 6600 GT": 146_000_000,
    "GeForce 6800 GT": 222_000_000,
    "GeForce 6800 Ultra": 222_000_000,
    "GeForce 7100 GS": 112_000_000,
    "GeForce 7300 LE": 112_000_000,
    "GeForce 7300 SE": 112_000_000,
    "GeForce 7600 GT": 177_000_000,
    "GeForce 7600 GS": 177_000_000,
    "GeForce 7800 GTX": 302_000_000,
    "GeForce 7900 GT": 278_000_000,
    "GeForce 7900 GTX": 278_000_000,
    "GeForce 7950 GX2": 556_000_000,  # 2x G71
    "GeForce 8400 GS": 210_000_000,
    "GeForce 8500 GT": 210_000_000,
    "GeForce 8800 GTS 320MB": 681_000_000,
    "GeForce 8800 GTX": 681_000_000,
    "GeForce 8800 GT": 754_000_000,
    "GeForce 8800 Ultra": 681_000_000,
    "GeForce 9300 GE": 210_000_000,
    "NVIDIA GeForce FX 5800 Ultra": 125_000_000,
    "NVIDIA GeForce 7950 GX2": 556_000_000,
    "NVIDIA GeForce 8800 Ultra": 681_000_000,
    "NVIDIA NV1": 1_000_000,

    # ================================================================
    # NVIDIA MODERN GPUs (GTX/RTX era)
    # ================================================================
    "GeForce GTX 260": 1_400_000_000,
    "GeForce GTX 280": 1_400_000_000,
    "GeForce GTX 295": 2_800_000_000,  # 2x GT200b
    "GeForce GTX 470": 3_000_000_000,
    "GeForce GTX 480": 3_000_000_000,
    "GeForce GTX 970": 5_200_000_000,
    "GeForce GTX 980 Ti": 8_000_000_000,
    "GeForce GTX 1080": 7_200_000_000,
    "GeForce RTX 2080 Ti": 18_600_000_000,
    "RTX 3080": 28_300_000_000,
    "GeForce RTX 3090": 28_300_000_000,
    "RTX 4090": 76_300_000_000,
    "Laptop GTX 860M": 1_870_000_000,  # GM107 variant
    "NVIDIA BlueField DPU": 500_000_000,  # SoC, not disclosed, rough est.
    "NVIDIA Tesla K80": 14_200_000_000,  # 2x GK210
    "NVIDIA Tesla P100": 15_300_000_000,
    "NVIDIA Tesla V100": 21_100_000_000,
    "NVIDIA A100": 54_200_000_000,
    "NVIDIA Jetson Nano": 2_000_000_000,  # Tegra X1 SoC

    # ================================================================
    # ATI / AMD GPUs
    # ================================================================
    "ATI 3D Rage (original)": 1_000_000,
    "ATI 3D Rage II": 2_000_000,
    "ATI Rage LT Pro": 4_800_000,
    "Radeon 7000": 30_000_000,
    "Radeon 7500": 30_000_000,
    "Radeon 8500": 60_000_000,
    "Radeon 9000 Pro": 36_000_000,
    "Radeon 9200 SE": 36_000_000,
    "Radeon 9200 LE": 36_000_000,
    "Radeon 9500 Pro": 107_000_000,
    "Radeon 9600 SE": 75_000_000,
    "Radeon 9700 Pro": 107_000_000,
    "Radeon 9800 Pro": 117_000_000,
    "Radeon 9800 XT": 117_000_000,
    "Radeon X300 SE": 67_000_000,
    "Radeon X300": 67_000_000,
    "Radeon X550": 67_000_000,
    "Radeon X600 SE": 75_000_000,
    "Radeon X600 Pro": 75_000_000,
    "Radeon X700 Pro": 110_000_000,
    "Radeon X800 Pro": 160_000_000,
    "Radeon X800 XT": 160_000_000,
    "Radeon X850 XT PE": 160_000_000,
    "Radeon X1050": 75_000_000,
    "Radeon X1300 Hypermemory": 120_000_000,
    "Radeon X1300": 120_000_000,
    "Radeon X1600 XT": 157_000_000,
    "Radeon X1800 XT": 321_000_000,
    "Radeon X1900 XT": 384_000_000,
    "Radeon X1950 Pro": 279_000_000,
    "Radeon X1950 XTX": 384_000_000,
    "Radeon Xpress 200": 25_000_000,
    "Radeon Xpress 1100": 50_000_000,
    "Radeon HD 2400 Pro": 180_000_000,
    "Radeon HD 2900 XT": 700_000_000,
    "Radeon HD 3450": 181_000_000,
    "Radeon HD 3870 X2": 1_330_000_000,
    "Radeon HD 4350": 242_000_000,
    "Radeon HD 4550": 242_000_000,
    "Radeon HD 4770": 826_000_000,
    "Radeon HD 4850": 956_000_000,
    "Radeon HD 4870": 956_000_000,
    "Radeon HD 5770": 1_040_000_000,
    "Radeon HD 5970": 4_340_000_000,
    "Radeon HD 6990": 5_340_000_000,
    "Radeon R9 280X": 4_313_000_000,
    "Radeon R9 290 Reference": 6_200_000_000,
    "Radeon R9 290X": 6_200_000_000,
    "Radeon R9 290": 6_200_000_000,
    "Radeon RX 480": 5_700_000_000,
    "Radeon RX 580": 5_700_000_000,
    "Radeon RX Vega 64": 12_500_000_000,
    "Radeon RX 7900 XTX": 57_700_000_000,
    "AMD FireStream 9170": 666_000_000,
    "MacBook Pro 2011 Radeon": 1_040_000_000,

    # ================================================================
    # OBSCURE 1990s GPUs
    # ================================================================
    "S3 ViRGE 325": 2_200_000,
    "S3 ViRGE/VX": 2_200_000,
    "S3 ViRGE/DX": 2_200_000,
    "S3 ViRGE/GX": 2_200_000,
    "S3 Trio3D/2X": 3_500_000,
    "S3 Trio3D": 3_000_000,
    "S3 Trio64V+": 1_000_000,
    "S3 Vision968": 1_100_000,
    "S3 Trio64V2/DX": 1_000_000,
    "S3 Savage 2000": 18_000_000,
    "S3 Savage3D": 8_000_000,
    "S3 Savage4": 9_000_000,
    "S3 Chrome S27": 70_000_000,
    "SiS 6326 AGP": 2_300_000,
    "SiS 6326": 2_300_000,
    "SiS 305": 4_000_000,
    "SiS 530": 6_000_000,
    "SiS 5598": 4_000_000,
    "SiS 620": 6_000_000,
    "SiS Mirage 1": 25_000_000,
    "SiS Mirage 2": 40_000_000,
    "SiS Mirage 3": 60_000_000,
    "SiS Xabre 400": 28_000_000,
    "Trident TGUI9440": 500_000,
    "Trident TGUI9680": 800_000,
    "Trident 3DImage 9750": 1_500_000,
    "Trident 3DImage 9850": 2_000_000,
    "Trident 9750 AGP": 1_500_000,
    "Trident Blade 3D": 3_500_000,
    "Trident Blade T64": 4_000_000,
    "Trident Blade XP": 8_000_000,
    "Alliance AT3D": 1_200_000,
    "Alliance ProMotion AT25": 1_500_000,
    "Alliance AT25 AGP": 1_500_000,
    "Cirrus Logic Laguna3D": 1_500_000,
    "Cirrus Logic GD5462": 1_500_000,
    "Cirrus Logic GD5465": 2_500_000,
    "Cirrus Logic GD7543": 600_000,
    "NeoMagic MagicGraph 128V": 800_000,
    "NeoMagic MagicGraph 128XD": 1_100_000,
    "Number Nine Imagine 128 II": 1_500_000,
    "Number Nine Revolution 3D": 3_000_000,
    "Oak OTI-87": 300_000,
    "Oak OTI-91": 400_000,
    "PowerVR PCX2": 2_500_000,
    "PowerVR KYRO II": 15_000_000,
    "Matrox Mystique 220": 2_800_000,
    "Matrox Mystique": 2_800_000,
    "Matrox Parhelia": 80_000_000,
    "Matrox G100": 3_000_000,
    "VIA Unichrome Pro": 15_000_000,
    "VIA Chrome9 HC3": 40_000_000,
    "VIA Chrome9 HC": 20_000_000,
    "VIA MVP3": 4_000_000,
    "Intel 740": 7_000_000,
    "Intel Extreme Graphics 2": 30_000_000,
    "Intel GMA 900": 40_000_000,
    "Intel GMA 950": 40_000_000,
    "Intel GMA 3100": 50_000_000,
    "Intel GMA X3100": 65_000_000,
    "Intel GMA 4500MHD": 80_000_000,
    "Intel 915G Integrated": 125_000_000,
    "XGI Volari V8 Duo": 25_000_000,

    # ================================================================
    # INTEL CPUs
    # ================================================================
    "Intel 4004": 2_300,
    "Intel 4040": 3_000,
    "Intel 8008": 3_500,
    "Intel 8080A": 4_500,
    "Intel 8080": 4_500,
    "Intel 8085": 6_500,
    "Intel 8048": 6_000,
    "Intel 8049": 6_000,
    "Intel 8086-2 10": 29_000,
    "Intel 8086-10": 29_000,
    "Intel 8086": 29_000,
    "Intel 8088-2 8": 29_000,
    "Intel 8088": 29_000,
    "Intel 80186 Embedded": 55_000,
    "Intel 80186": 55_000,
    "Intel 80188": 55_000,
    "Intel 80286-20": 134_000,
    "Intel 80286": 134_000,
    "Intel 80376": 275_000,
    "Intel 80386DX-33": 275_000,
    "Intel 80386DX": 275_000,
    "Intel 80386SX": 275_000,
    "Intel 80486DX4": 1_600_000,
    "Intel 80486DX2-50": 1_200_000,
    "Intel 80486DX2": 1_200_000,
    "Intel 80486DX": 1_200_000,
    "Intel 80486SX": 1_185_000,
    "Intel 486DX2-66": 1_200_000,
    "Intel Pentium 90": 3_100_000,
    "Intel Pentium 133": 3_300_000,
    "Intel Pentium 166 MMX": 4_500_000,
    "Intel Pentium 200 MMX": 4_500_000,
    "Pentium MMX Mobile ES": 4_500_000,
    "Pentium MMX 200": 4_500_000,
    "Intel Pentium MMX Overdrive": 4_500_000,
    "Pentium OverDrive 150 ES": 3_300_000,
    "Intel Pentium Pro 200": 5_500_000,
    "Pentium Pro 133 ES": 5_500_000,
    "Pentium Pro 200 ES": 5_500_000,
    "Intel Pentium II 233": 7_500_000,
    "Intel Pentium II 400": 7_500_000,
    "Pentium II 266 ES": 7_500_000,
    "Pentium II Deschutes ES": 7_500_000,
    "Pentium II Xeon 400 ES": 7_500_000,
    "Pentium II Engineering Board": 7_500_000,
    "Intel Celeron 300A": 19_000_000,
    "Intel Celeron 400": 19_000_000,
    "Intel Pentium III 450": 9_500_000,
    "Intel Pentium III 600": 9_500_000,
    "Intel Pentium III 1 GHz": 28_100_000,
    "Pentium III 450 ES": 9_500_000,
    "Pentium III Coppermine ES": 28_100_000,
    "Pentium III Xeon ES": 9_500_000,
    "Pentium III 800": 28_100_000,
    "Intel Pentium 4 3.8 GHz": 125_000_000,
    "Intel Pentium 4 7.0 GHz": 125_000_000,
    "Intel Pentium 4 3.0 GHz": 55_000_000,
    "Pentium 4 3.0 GHz": 55_000_000,
    "Intel Core 2 Duo E8400": 410_000_000,
    "Intel Core 2 Duo E8600": 410_000_000,
    "Intel Core i5-2500K": 1_160_000_000,
    "Intel Core i7-920": 731_000_000,
    "Intel Core i7-2600K": 1_160_000_000,
    "Intel Core i7-4790K": 1_400_000_000,
    "Intel Core i7-6700K": 1_750_000_000,
    "Intel Core i7-7700K": 1_750_000_000,
    "Intel Core i7-8700K": 3_000_000_000,
    "Intel Core i7-980X": 1_170_000_000,
    "Intel Core i9-9900K": 3_000_000_000,
    "Intel Core i9-10900K": 3_100_000_000,
    "Intel Core i9-12900KS": 12_000_000_000,  # est. for Alder Lake
    "Intel Core i9-13900KS": 12_000_000_000,  # Raptor Lake, similar die
    "Intel Core i9-14900KF": 12_000_000_000,  # same die as 13900K
    "Intel iAPX 432": 110_000,
    "Intel Itanium 2 (McKinley)": 221_000_000,
    "Intel Itanium 2 (Montecito)": 1_720_000_000,
    "Intel i960CA": 600_000,
    "Intel 80960CA": 600_000,
    "Intel StrongARM SA-110": 2_500_000,
    "StrongARM SA-110 ES": 2_500_000,
    "StrongARM SA-1110 ES": 2_500_000,
    "Intel Xeon Phi 7120P": 5_000_000_000,
    "Intel Xeon Phi Knights Corner": 5_000_000_000,
    "Intel Larrabee": 2_000_000_000,
    "Intel MCS-4": 2_300,
    "Intel MCS-8": 3_500,

    # ================================================================
    # AMD CPUs
    # ================================================================
    "AMD Am5x86": 1_600_000,
    "AMD K5 PR166": 4_300_000,
    "AMD K6-233": 8_800_000,
    "AMD K6-2 550": 9_300_000,
    "AMD K6-2 350": 9_300_000,
    "AMD K6-2 400": 9_300_000,
    "AMD K6-2 500": 9_300_000,
    "AMD K6-III 450": 21_300_000,
    "AMD Athlon 500": 22_000_000,
    "AMD Athlon 64 FX-57": 114_000_000,
    "Athlon XP 2500+": 54_300_000,
    "AMD FX-8350 LN2": 1_200_000_000,
    "AMD FX-8350": 1_200_000_000,
    "AMD FX-9590": 1_200_000_000,
    "AMD Ryzen 5 1600": 4_800_000_000,
    "AMD Ryzen 7 2700X": 4_800_000_000,
    "AMD Ryzen 7 3700X": 5_990_000_000,
    "AMD Ryzen 9 3950X": 9_890_000_000,
    "AMD Ryzen 9 5950X": 10_400_000_000,
    "AMD 29K": 120_000,
    "AMD 80286-12": 134_000,
    "AMD 8086-10": 29_000,

    # ================================================================
    # OTHER x86
    # ================================================================
    "Cyrix 6x86-P166+": 3_000_000,
    "Cyrix 6x86MX MII-300": 6_500_000,
    "Cyrix 6x86MX ES": 6_500_000,
    "Cyrix MII 333 ES": 6_500_000,
    "IDT WinChip C6": 5_400_000,
    "WinChip 2 ES": 5_400_000,
    "VIA C3 533 Ezra": 15_200_000,
    "NEC V20": 63_000,
    "NEC V30": 63_000,
    "NEC V40H": 63_000,
    "Transmeta Crusoe TM5600": 36_800_000,
    "Transmeta Crusoe Proto": 36_800_000,
    "Transmeta Efficeon TM8600": 130_000_000,
    "National Semiconductor Geode": 2_400_000,
    "National Semiconductor NS16032": 68_000,
    "National Semiconductor NS32016": 68_000,
    "National Semiconductor NS32032": 70_000,
    "IBM 6x86MX": 6_500_000,

    # ================================================================
    # RISC / WORKSTATION / EXOTIC CPUs
    # ================================================================
    "DEC Alpha 21064": 1_680_000,
    "DEC Alpha 21164": 9_300_000,
    "DEC Alpha 21264": 15_200_000,
    "Alpha EV5 21164": 9_300_000,
    "Alpha EV6 21264": 15_200_000,
    "Alpha 21066A": 1_800_000,
    "HP PA-7000": 580_000,
    "HP PA-7100LC": 900_000,
    "HP PA-7200": 1_260_000,
    "HP PA-7300LC": 9_200_000,
    "HP PA-8000": 3_800_000,
    "HP PA-8200": 3_800_000,
    "HP PA-8500": 140_000_000,
    "HP PA-8900": 300_000_000,
    "HP FOCUS": 450_000,
    "Sun SuperSPARC": 3_100_000,
    "Sun UltraSPARC II": 5_400_000,
    "UltraSPARC IIi": 5_400_000,
    "Sun Niagara T1": 300_000_000,
    "SUN Niagara T1": 300_000_000,
    "SPARC V7": 800_000,
    "SPARC microSPARC-II": 2_300_000,
    "MIPS R2000": 110_000,
    "MIPS R3000": 120_000,
    "MIPS R4000": 1_350_000,
    "MIPS R8000": 2_600_000,
    "MIPS R10000": 6_700_000,
    "MIPS R12000": 6_900_000,
    "NEC VR4300": 1_700_000,
    "IBM POWER1": 6_900_000,
    "IBM POWER2": 23_000_000,
    "IBM POWER4": 174_000_000,
    "IBM POWER7": 1_200_000_000,
    "IBM PowerPC 601": 2_800_000,
    "IBM PowerPC 604": 3_600_000,
    "IBM PowerPC 750": 6_350_000,
    "IBM Cell Broadband Engine": 241_000_000,
    "IBM RS/6000 POWER": 6_900_000,
    "IBM PowerAI AC922": 241_000_000,  # POWER9 + GPU node

    # Motorola 68k
    "Motorola 68000 ES": 68_000,
    "Motorola 68000": 68_000,
    "Motorola 68008": 70_000,
    "Motorola 68010": 84_000,
    "Motorola 68020": 190_000,
    "Motorola 68030": 273_000,
    "Motorola 68040": 1_200_000,
    "Motorola MC14500B": 500,

    # Other exotic CPUs
    "Inmos Transputer T414": 200_000,
    "Inmos Transputer T800": 300_000,
    "Fairchild Clipper": 132_000,
    "Elbrus 2000": 25_500_000,
    "Sun MAJC": 116_000_000,
    "Western Electric WE32100": 150_000,
    "Zilog Z80H": 8_500,
    "Zilog Z180": 10_000,
    "Zilog Z8000 Weird": 17_500,
    "Zilog Z8000": 17_500,
    "Zilog Z80000": 91_000,
    "Zilog Z80 Counterfeit": 8_500,
    "Zilog Z80 CPU Card": 8_500,
    "Zilog Z80A": 8_500,
    "Zilog Z80": 8_500,
    "MOS 65C02": 11_500,
    "Acorn ARM1": 25_000,
    "Acorn ARM2": 30_000,
    "DEC MicroVAX 78032": 125_000,
    "VAX 11/780": 100_000,
    "Hitachi SuperH-4": 10_500_000,
    "Sony Emotion Engine": 10_500_000,
    "Pentium Pro 200": 5_500_000,

    # ================================================================
    # TPUs
    # ================================================================
    "Google TPU v1 Board": 24_000_000_000,
    "Google TPU v1 Test": 24_000_000_000,
    "Google TPU v2 Chip": 30_000_000_000,
    "Google TPU v2 Board": 120_000_000_000,
    "Google TPU v3 Board": 42_000_000_000,
    "Google TPU v3 Pod": 168_000_000_000,  # 4x v3
    "Google TPU \u00abIronwood": 50_000_000_000,  # est.
    "Edge TPU USB": 15_000_000,

    # ================================================================
    # NPUs
    # ================================================================
    "Intel Movidius NCS (Myriad 2)": 150_000_000,
    "Intel Movidius NCS2": 350_000_000,
    "Apple Neural Engine (A11)": 600_000_000,
    "Apple M1 Neural Engine": 2_600_000_000,
    "Qualcomm Hexagon": 300_000_000,

    # ================================================================
    # PHYSICS / COPROCESSORS
    # ================================================================
    "AGEIA PhysX P1 PPU": 125_000_000,
    "BFG PhysX P1": 125_000_000,
    "ASUS PhysX P1": 125_000_000,
    "AGEIA PhysX P2": 125_000_000,
    "AGEIA PhysX PPU": 125_000_000,
    "NVIDIA PhysX-on-GPU Mode": 0,  # software mode
    "NVIDIA PhysX-on-Secondary": 0,  # software mode
    "Havok FX GPU Physics": 0,  # software concept
    "Weitek 1167 RISC": 56_000,
    "Weitek 1167 Math": 56_000,
    "Intel 80287": 45_000,
    "Intel 8087 FPU": 45_000,
    "Motorola 68881 FPU": 155_000,
    "Motorola 68881": 155_000,

    # ================================================================
    # ASIC MINERS
    # ================================================================
    "Antminer S1 ": 60_000_000,  # BM1380
    "Antminer S1": 60_000_000,
    "Antminer S3 Rustbucket": 150_000_000,
    "Antminer S3": 150_000_000,  # BM1382
    "Antminer S5": 200_000_000,  # BM1384
    "Antminer S7": 250_000_000,  # BM1385
    "Antminer S9 Overclocked Firestarter": 400_000_000,
    "Antminer S9 \u00abBurned Pins": 400_000_000,
    "Antminer S9 \u00abWinter Heater": 400_000_000,
    "Antminer S9 \u00abDead Chain": 400_000_000,
    "Overclocked S9": 400_000_000,
    "Antminer S9j": 400_000_000,
    "Antminer S9i": 400_000_000,
    "Antminer S9": 400_000_000,  # BM1387
    "Antminer S11": 400_000_000,  # BM1387
    "Antminer S15": 600_000_000,  # BM1391
    "Antminer S17 Fragile": 800_000_000,
    "Antminer S17+ ": 800_000_000,
    "Antminer S17 Hashboard Zombie": 800_000_000,
    "Antminer S17 Shorted": 800_000_000,
    "Antminer S17 Heatsink": 800_000_000,
    "Antminer S17+": 800_000_000,
    "Antminer S17 Pro": 800_000_000,
    "Antminer S17": 800_000_000,  # BM1397
    "S17+": 800_000_000,
    "Antminer S19 XP": 1_500_000_000,  # BM1399
    "Antminer S19K Pro": 1_500_000_000,
    "Antminer S19j Pro": 1_000_000_000,
    "Antminer S19j": 1_000_000_000,
    "Antminer S19 Pro": 1_000_000_000,
    "Antminer S19 \u00abDatacenter": 1_000_000_000,
    "Antminer S19": 1_000_000_000,  # BM1398
    "Antminer S21 XP": 3_000_000_000,
    "Antminer S21 Hydro": 3_000_000_000,
    "Antminer S21 Pro": 2_500_000_000,
    "Antminer S21": 2_500_000_000,  # BM1370
    "WhatsMiner M30S+": 800_000_000,
    "WhatsMiner M50S": 1_500_000_000,
    "WhatsMiner \u00abHot Shelf": 800_000_000,
    "AvalonMiner 1246": 700_000_000,
    "AvalonMiner 1366": 1_200_000_000,
    "Avalon Miner \u00abFanless": 700_000_000,
    "Avalon \u00abFan Error": 700_000_000,
    "Avalon Batch 1": 10_000_000,  # A3256
    "Avalon Batch 2": 10_000_000,
    "Avalon Batch 3": 10_000_000,
    "Avalon Prototype ES": 10_000_000,
    "Avalon USB Nano": 10_000_000,
    "Avalon FPGA Prototype": 90_000_000,  # FPGA
    "Avalon-1 Fanless": 10_000_000,
    "Avalon-1 Side-Panel": 10_000_000,
    "Avalon-1 \u00abMuseum": 10_000_000,
    "Avalon ASIC Test": 8_000_000,
    "ASICMiner Block Erupter Overclocked": 10_000_000,
    "ASICMiner Block Erupter USB": 10_000_000,
    "ASICMiner Block Erupter": 10_000_000,
    "ASICMiner Blade": 10_000_000,
    "ASICMiner Immersion": 10_000_000,
    "Butterfly Labs Jalapeno Overvolted": 75_000_000,
    "Butterfly Labs Jalapeno Watercooled": 75_000_000,
    "Butterfly Labs Jalapeno": 75_000_000,
    "Butterfly Labs 25": 75_000_000,
    "Butterfly Labs 50": 75_000_000,
    "Butterfly Labs Single-Chip ES": 50_000_000,
    "Butterfly Labs FPGA": 90_000_000,  # FPGA
    "DIY Overvolted Jalapeno": 75_000_000,
    "USB Hub of 10 Block Erupters": 100_000_000,  # 10x BE100
    "ASIC \u00abMystery Repair": 800_000_000,  # S17/S19 era est.
    "Early SHA-256 ASIC Test Die": 5_000_000,
    "Canaan Avalon Chip-on-Board ES": 8_000_000,

    # ================================================================
    # FPGAs (used as miners, categorized as DSP/DSC)
    # ================================================================
    "Xilinx Spartan-6 LX150": 90_000_000,
    "Open Source Spartan-6 Quad": 90_000_000,
    "Open Source Spartan-6 Mini": 43_000_000,
    "Open-Source Spartan-6 Mini": 43_000_000,
    "Early Single-FPGA USB": 43_000_000,
    "Ultra-Low-Cost DIY FPGA": 43_000_000,
    "Altera Cyclone IV": 150_000_000,
    "Beauty-and-the-Beast": 150_000_000,
    "K16 FPGA": 90_000_000,
    "FPGA Mining \u00abPizza Box": 90_000_000,
    "FPGA Test Bench": 90_000_000,
    "FPGA \u00abHashBackpack": 90_000_000,
    "Rackmount 1U FPGA": 90_000_000,
    "Open-Source Spartan-6": 43_000_000,
    "Generic 2012 FPGA PCIe": 90_000_000,
    "Clustered Spartan-6": 360_000_000,  # 4x
    "Homemade FPGA-in-a-Toaster": 90_000_000,
    "FPGA Development Kit Hash": 43_000_000,
    "Open Source FPGA \u00abLearning": 43_000_000,
    "Rack of Retired FPGA": 900_000_000,  # many units
    "FPGA \u00abPrototype": 43_000_000,

    # ================================================================
    # MCUs
    # ================================================================
    "Intel 8051": 12_000,
    "Intel 8031": 12_000,
    "Intel 8751": 12_000,
    "Intel 8042 Keyboard MCU": 8_000,
    "Intel 8042": 8_000,
    "Intel 8096": 56_000,
    "Intel 8048 Keyboard": 6_000,
    "Intel 8048": 6_000,
    "Intel 8049": 6_000,
    "Motorola 68HC11F1": 45_000,
    "Motorola 68HC12A4": 175_000,
    "Motorola 68HC16Z1": 85_000,
    "Motorola 68HC11": 35_000,
    "Motorola 68HC05": 12_500,
    "Motorola 68HC12": 150_000,
    "Motorola MC146870": 50_000,
    "Zilog Z8": 9_000,
    "Zilog Z86Cxx": 15_000,
    "Hitachi HD6301": 15_000,
    "Hitachi HD6303": 20_000,
    "Hitachi H8/300": 65_000,
    "Mostek MK3870": 8_000,
    "Mostek MK6800": 4_100,
    "Mostek MK3850 F8": 4_000,
    "Philips MAB8051": 12_000,
    "Philips 87C751": 12_000,
    "Philips 87C552": 40_000,
    "Siemens SAB80515": 20_000,
    "Siemens SAB80C517": 30_000,
    "Microchip PIC16C54": 4_000,
    "Microchip PIC16C57": 5_000,
    "Microchip PIC16C84": 10_000,
    "Microchip PIC16F84": 12_000,
    "Microchip PIC16F877": 50_000,
    "Microchip PIC17C756": 30_000,
    "Microchip PIC18C452": 60_000,
    "Atmel AT90S1200": 13_000,
    "Atmel AT90S2313": 15_000,
    "Atmel AT90S8515": 20_000,
    "Atmel ATmega103": 100_000,
    "Atmel ATmega8": 65_000,
    "STMicroelectronics ST9": 20_000,
    "STMicroelectronics ST10": 150_000,
    "NEC V850": 60_000,
    "NEC \u00b5PD7810": 30_000,
    "NEC \u00b5PD8049": 6_000,
    "Renesas H8/300H": 65_000,
    "Renesas H8S": 100_000,
    "Texas Instruments MSP430C11x": 20_000,
    "Texas Instruments MSP430F149": 50_000,
    "TI TMS 1000": 8_000,
    "TI TMS 9900 Evaluation": 8_000,
    "TI TMS 9900": 8_000,
    "TI TMS 9980": 8_000,
    "Signetics 8X300": 10_000,
    "OKI MSM80C85": 6_500,
    "Fujitsu MB8843": 8_000,
    "Sharp IR Controller": 10_000,

    # ================================================================
    # DSPs
    # ================================================================
    "TMS32010": 52_000,
    "TMS320C10-25": 55_000,
    "TMS320C15": 65_000,
    "TMS320C25": 92_000,
    "TMS320C31": 500_000,
    "TMS320C40": 1_500_000,
    "TMS320C54x": 4_000_000,
    "Analog Devices ADSP-2100": 95_000,
    "Analog Devices ADSP-2101": 190_000,
    "Analog Devices ADSP-2105": 165_000,
    "Analog Devices ADSP-21060 SHARC": 2_750_000,
    "Motorola DSP56001": 350_000,
    "Motorola DSP56301": 2_500_000,
    "NEC \u00b5PD7720": 35_000,
    "NEC \u00b5PD77016": 750_000,
    "AT&T DSP-1": 25_000,
    "Lucent DSP1600": 300_000,
    "Cirrus Logic CS49300": 3_500_000,
    "Fujitsu MB86233 DSP": 750_000,
    "Sony CXD2500 DSP": 400_000,
    "Freescale DSP56800": 1_500_000,

    # ================================================================
    # AUDIO / PERIPHERAL COPROCESSORS
    # ================================================================
    "Intel 8253 Programmable Interval Timer": 8_500,
    "Intel 8255 PPI": 6_000,
    "Intel 82C54 PIT": 11_000,
    "Intel 8259A Programmable Interrupt": 6_000,
    "Intel 8279 Keyboard/Display": 6_000,
    "Motorola 6845 CRT": 12_500,
    "MOS 6522 VIA": 9_000,
    "MOS 6526 CIA": 11_000,
    "Zilog Z8530 SCC": 17_500,
    "Yamaha YMF262": 400_000,
    "Yamaha YM2149": 6_500,
    "Yamaha YM2203": 40_000,
    "Philips SAA1099": 12_500,
    "Dallas DS1287 RTC": 12_500,
    "Dallas DS12887 RTC": 17_500,
    "Crystal CS4231": 75_000,
    "Maxim MAX232": 350,
    "Hitachi HD44780": 7_500,

    # ================================================================
    # EARLY 1960s CUSTOM ICs
    # ================================================================
    "MECL-I ECL Logic Slice": 6,
    "Molecular Electronic Computer": 2,
    "Apollo Guidance Computer Logic IC": 18,
    "CDC 6600 Logic Gate Array": 8,
    "IBM System/360 SLT Module": 4,
    "Four-Phase AL1 Bit-Slice": 250,
    "RCA MOS LSI Test Chip": 75,
    "RCA MOS Calculator Slice": 350,
    "RCA COS/MOS Logic Demo": 35,
    "TI Calculator Logic IC": 75,
    "IBM 7030 Stretch ECL Module": 3,
    "Honeywell 200 IC Logic Card": 8,
    "UNIVAC 1107 Thin-Film Memory": 0,  # not transistor-based
    "NCR 315 Integrated Logic Block": 6,
    "Burroughs B5000 Stack IC": 4,
    "Minuteman Guidance LSI Block": 150,
    "Semiconductor Network Computer Block": 3,
    "IBM Solid Logic Technology Pack": 4,
    "Motorola Early MOS Clock Chip": 350,
    "TI MOS Watch/Clock Prototype": 350,

    # ================================================================
    # SOC ENTRIES
    # ================================================================
    "Motorola 68020 CPU Card": 190_000,

    # ================================================================
    # REMAINING CPUs from 1970s section
    # ================================================================
    "National SC/MP": 5_000,
    "National Semiconductor IMP-16": 3_000,
    "Signetics 2650": 3_000,
    "Rockwell PPS-4": 2_000,
    "Rockwell PPS-8": 3_500,
    "Fairchild PPS-25": 2_500,
    "Fairchild F8": 4_000,
    "RCA CDP1802 COSMAC": 5_000,
    "RCA CDP1802 Space-Grade": 5_000,
    "RCA CDP1802": 5_000,
    "RCA CDP1801": 3_000,
    "RCA CDP1804": 6_000,
    "MOS Technology 6502": 3_510,
    "MOS 6502A": 3_510,
    "MOS 6507": 3_510,
    "MOS 6510": 3_510,
    "Fujitsu MB8861": 4_000,
    "Hitachi HD46800": 4_100,
    "Sharp LH0080": 8_500,  # Z80 clone

    # Remaining misc
    "Mostek MK6800 Evaluation": 4_100,
    "PA-RISC Laptop Proto": 900_000,
    "PA-7200 ES": 1_260_000,

    # Entries with special chars that get mangled by encoding
    "Google TPU Ironwood": 50_000_000_000,
    "Avalon Miner Fanless Experiment": 700_000_000,
    "WhatsMiner Hot Shelf Hero": 800_000_000,
    "ASIC Mystery Repair Shop": 800_000_000,
    "Avalon Fan Error Festival": 700_000_000,
    "FPGA Mining Pizza Box": 90_000_000,
    "FPGA HashBackpack": 90_000_000,
    "Avalon-1 Museum Edition": 10_000_000,
    "Open Source FPGA Learning Miner": 43_000_000,
    "Tadpole SPARCbook UltraSPARC": 5_400_000,
    "UNIVAC 1107 Thin-Film": 0,
    "NEC PD77016": 750_000,
    "NEC PD7810": 30_000,
    "NEC PD8049": 6_000,
    "NEC PD7720": 35_000,

    # Plain Motorola entries (no "68000" prefix)
    "Motorola 6800": 4_100,
    "Motorola 6801": 5_000,
    "Motorola 6809": 9_000,

    # ================================================================
    # FICTIONAL / POP-CULTURE ENTRIES (mythic rarity)
    # ================================================================
    "Aperture Science TensorCore": 999_999_999_999,  # SPAAAACE!
    "GLaDOS Neural Nexus Core": 420_000_000_000,
    "RobCo Pip-Boy 3000 Processor": 77_000_000,
    "HAL 9000 Heuristic Processing Unit": 9_000_000_000,
    "Cyberdyne T-800 Neural Net Processor": 800_000_000_000,
    "DOOM IDKFA Compute Slab": 666_000_000,
}


def parse_power_draw(val: str) -> float:
    """Convert power_draw string like '30 W', '20 MW', '900 kW' to watts."""
    if not val or not val.strip():
        return 0.0
    val = val.strip()
    m = re.match(r"([\d.]+)\s*(MW|kW|W)", val, re.IGNORECASE)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "MW":
        return num * 1_000_000
    elif unit == "KW":
        return num * 1_000
    return num


def _normalize(s: str) -> str:
    """Strip non-ASCII and collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "", s)).strip().lower()


# Pre-compute sorted keys (longest first) with normalized forms
_SORTED_KEYS = sorted(TRANSISTORS.keys(), key=len, reverse=True)
_NORM_KEYS = [(_normalize(k), k) for k in _SORTED_KEYS]


def find_transistors(name: str) -> int:
    """Look up transistor count by matching name against the lookup dict.
    Tries longest key match first for specificity. Strips non-ASCII for fuzzy matching."""
    name_norm = _normalize(name)
    for norm_key, orig_key in _NORM_KEYS:
        if norm_key in name_norm:
            return TRANSISTORS[orig_key]
    return 0


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "..", "trash2.csv")
    csv_path = os.path.normpath(csv_path)

    # Read all rows
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Stats
    total = len(rows)
    matched = 0
    datacenter_array = 0
    unmatched = []

    for row in rows:
        cat = row.get("category", "").strip().upper()
        name = row.get("name", "")

        if cat in ("DATACENTER", "ARRAY"):
            row["transistors"] = 0
            datacenter_array += 1
        else:
            t = find_transistors(name)
            row["transistors"] = t
            if t > 0:
                matched += 1
            else:
                unmatched.append(f"  [{cat}] {name}")

    # Add transistors to fieldnames (replace trailing empty columns)
    # Original header: name,manufacturer,category,year,hashrate,power_draw,rarity,description,,,
    clean_fields = [f for f in fieldnames if f.strip()]
    if "transistors" not in clean_fields:
        clean_fields.append("transistors")

    # Write back
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=clean_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerow({})  # empty row? no, let's just write data
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in clean_fields})

    # Actually let's rewrite without that empty row
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=clean_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in clean_fields})

    print(f"Done! {total} rows processed.")
    print(f"  DATACENTER/ARRAY (transistors=0): {datacenter_array}")
    print(f"  Chip entries matched: {matched}")
    print(f"  Unmatched (transistors=0): {len(unmatched)}")
    if unmatched:
        print("\nUnmatched entries:")
        for u in unmatched:
            print(u.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
