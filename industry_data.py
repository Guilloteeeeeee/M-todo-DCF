"""Promedios por industria de Damodaran (enero 2026): US y Global. Generado desde sus planillas."""
# Prima de riesgo de mercado (prima implícita de EE.UU., Damodaran, ERPbymonth: "ERP (T12m)" de oct-2026, medida sobre el bono crudo a 10 años).
# Se actualiza A MANO cada 4-6 meses: cambiar los dos valores de abajo. La app avisa cuando pasan más de ERP_MAX_MESES.
ERP_DAMODARAN = 0.0370
ERP_DATE = "octubre 2026"
ERP_DATE_ISO = "2026-10-01"
ERP_MAX_MESES = 6


def erp_age_days(today=None) -> int:
    """Días desde la fecha de la prima de Damodaran cargada en ERP_DATE_ISO."""
    from datetime import date
    return ((today or date.today()) - date.fromisoformat(ERP_DATE_ISO)).days


def erp_is_stale(today=None) -> bool:
    """True si la prima cargada tiene más de ERP_MAX_MESES meses (≈ 30,4 días por mes)."""
    return erp_age_days(today) > ERP_MAX_MESES * 30.4
DATE = "enero 2026"
DATE_ISO = "2026-01-01"   # fecha de las tablas de Damodaran (la app avisa si pasaron más de 12 meses)


def reference_status(today=None):
    """v2.44: lista de los datos de referencia que hay que renovar a mano, con su fecha, su edad y si ya pasó el plazo.
    Devuelve [{'nombre','fecha','meses','limite_meses','vencida','donde'}]. Para agregar otra tabla, sumar una fila a _ITEMS."""
    from datetime import date
    from damodaran_map import DAM_FILE_DATE, DAM_FILE_ISO
    hoy = today or date.today()
    items = [
        ("Prima de riesgo de mercado (ERP)", ERP_DATE, ERP_DATE_ISO, ERP_MAX_MESES,
         "Damodaran → Data → ERPbymonth, columna «ERP (T12m)»; se cambia en industry_data.py (ERP_DAMODARAN, ERP_DATE, ERP_DATE_ISO)"),
        ("Tablas por industria, riesgo país e impuestos", DATE, DATE_ISO, 12,
         "Damodaran → Data → tablas de enero (betas, márgenes, ROC por industria; riesgo país; impuestos)"),
        ("Planilla de empresas por industria", DAM_FILE_DATE, DAM_FILE_ISO, 12,
         "Damodaran → «Companies in each industry» (indname.xls); se rehace damodaran_companies.tsv.gz"),
    ]
    out = []
    for nombre, fecha, iso, limite, donde in items:
        dias = (hoy - date.fromisoformat(iso)).days
        out.append(dict(nombre=nombre, fecha=fecha, meses=dias / 30.4, limite_meses=limite, vencida=dias > limite * 30.4, donde=donde))
    return out
IND = {
"Advertising": {
"us": {
"n": 52,
"beta": 1.2105,
"de": 0.402,
"tax": 0.0502,
"ubeta": 1.008,
"wacc": 0.0781,
"ke": 0.0935,
"margin": 0.1007,
"netm": -0.003,
"roe": -0.0134,
"roc": 0.2772
},
"gl": {
"n": 419,
"beta": 1.2728,
"de": 0.4055,
"tax": 0.1347,
"ubeta": 1.0861,
"wacc": 0.092,
"ke": 0.1112,
"margin": 0.0855,
"netm": 0.0139,
"roe": 0.0312,
"roc": 0.1793
}
},
"Aerospace/Defense": {
"us": {
"n": 79,
"beta": 0.9455,
"de": 0.1556,
"tax": 0.1158,
"ubeta": 0.8694,
"wacc": 0.076,
"ke": 0.0817,
"margin": 0.0865,
"netm": 0.0499,
"roe": 0.1527,
"roc": 0.1601
},
"gl": {
"n": 319,
"beta": 1.2309,
"de": 0.13,
"tax": 0.1093,
"ubeta": 1.1667,
"wacc": 0.1014,
"ke": 0.1088,
"margin": 0.0918,
"netm": 0.0665,
"roe": 0.1845,
"roc": 0.1546
}
},
"Air Transport": {
"us": {
"n": 23,
"beta": 1.1855,
"de": 0.9117,
"tax": 0.0829,
"ubeta": 0.7579,
"wacc": 0.0672,
"ke": 0.0924,
"margin": 0.0532,
"netm": 0.0251,
"roe": 0.1419,
"roc": 0.0793
},
"gl": {
"n": 150,
"beta": 0.9906,
"de": 0.7889,
"tax": 0.1462,
"ubeta": 0.6841,
"wacc": 0.0723,
"ke": 0.0953,
"margin": 0.0821,
"netm": 0.0491,
"roe": 0.1728,
"roc": 0.0901
}
},
"Apparel": {
"us": {
"n": 35,
"beta": 0.9359,
"de": 0.3129,
"tax": 0.0961,
"ubeta": 0.7946,
"wacc": 0.0713,
"ke": 0.0812,
"margin": 0.0911,
"netm": 0.0385,
"roe": 0.1042,
"roc": 0.1577
},
"gl": {
"n": 1207,
"beta": 0.7624,
"de": 0.187,
"tax": 0.1524,
"ubeta": 0.7053,
"wacc": 0.0762,
"ke": 0.0824,
"margin": 0.1259,
"netm": 0.069,
"roe": 0.1354,
"roc": 0.1607
}
},
"Auto & Truck": {
"us": {
"n": 33,
"beta": 1.4565,
"de": 0.197,
"tax": 0.0374,
"ubeta": 1.3082,
"wacc": 0.0938,
"ke": 0.1045,
"margin": 0.0232,
"netm": 0.0129,
"roe": 0.0316,
"roc": 0.0225
},
"gl": {
"n": 165,
"beta": 1.406,
"de": 0.4781,
"tax": 0.1157,
"ubeta": 1.1454,
"wacc": 0.0948,
"ke": 0.1187,
"margin": 0.0431,
"netm": 0.0308,
"roe": 0.0623,
"roc": 0.0433
}
},
"Auto Parts": {
"us": {
"n": 35,
"beta": 1.3394,
"de": 0.4146,
"tax": 0.15,
"ubeta": 1.1283,
"wacc": 0.0818,
"ke": 0.0992,
"margin": 0.0567,
"netm": 0.0072,
"roe": 0.0217,
"roc": 0.0898
},
"gl": {
"n": 797,
"beta": 1.4498,
"de": 0.278,
"tax": 0.1728,
"ubeta": 1.3535,
"wacc": 0.1042,
"ke": 0.1211,
"margin": 0.0545,
"netm": 0.029,
"roe": 0.0656,
"roc": 0.1292
}
},
"Bank (Money Center)": {
"us": {
"n": 15,
"beta": 0.761,
"de": 1.6419,
"tax": 0.1843,
"ubeta": 0.4439,
"wacc": 0.0498,
"ke": 0.0734,
"margin": 0.0,
"netm": 0.2889,
"roe": 0.1286,
"roc": None
},
"gl": {
"n": 604,
"beta": 0.6975,
"de": 2.1172,
"tax": 0.2159,
"ubeta": 0.3628,
"wacc": 0.0529,
"ke": 0.0788,
"margin": 0.0038,
"netm": 0.3492,
"roe": 0.1154,
"roc": None
}
},
"Banks (Regional)": {
"us": {
"n": 568,
"beta": 0.3985,
"de": 0.521,
"tax": 0.1761,
"ubeta": 0.3744,
"wacc": 0.0498,
"ke": 0.0573,
"margin": 0.0,
"netm": 0.2749,
"roe": 0.0975,
"roc": None
},
"gl": {
"n": 825,
"beta": 0.5135,
"de": 2.0228,
"tax": 0.1836,
"ubeta": 0.3004,
"wacc": 0.0499,
"ke": 0.0684,
"margin": -0.0,
"netm": 0.3031,
"roe": 0.0874,
"roc": None
}
},
"Beverage (Alcoholic)": {
"us": {
"n": 14,
"beta": 0.8125,
"de": 0.4334,
"tax": 0.1235,
"ubeta": 0.628,
"wacc": 0.0648,
"ke": 0.0757,
"margin": 0.2276,
"netm": 0.0056,
"roe": 0.0057,
"roc": 0.1574
},
"gl": {
"n": 217,
"beta": 0.7927,
"de": 0.2029,
"tax": 0.1762,
"ubeta": 0.725,
"wacc": 0.0772,
"ke": 0.0841,
"margin": 0.2247,
"netm": 0.1246,
"roe": 0.1369,
"roc": 0.1542
}
},
"Beverage (Soft)": {
"us": {
"n": 27,
"beta": 0.6415,
"de": 0.2059,
"tax": 0.0685,
"ubeta": 0.5755,
"wacc": 0.0633,
"ke": 0.0681,
"margin": 0.2053,
"netm": 0.134,
"roe": 0.3092,
"roc": 0.2903
},
"gl": {
"n": 94,
"beta": 0.5928,
"de": 0.1872,
"tax": 0.133,
"ubeta": 0.542,
"wacc": 0.0682,
"ke": 0.0729,
"margin": 0.1762,
"netm": 0.1147,
"roe": 0.2599,
"roc": 0.2537
}
},
"Broadcasting": {
"us": {
"n": 24,
"beta": 0.4708,
"de": 0.8585,
"tax": 0.0773,
"ubeta": 0.3153,
"wacc": 0.0509,
"ke": 0.0605,
"margin": 0.1233,
"netm": 0.0206,
"roe": 0.0399,
"roc": 0.1457
},
"gl": {
"n": 127,
"beta": 0.8322,
"de": 0.5677,
"tax": 0.152,
"ubeta": 0.6558,
"wacc": 0.0707,
"ke": 0.0864,
"margin": 0.0997,
"netm": 0.0343,
"roe": 0.0447,
"roc": 0.0951
}
},
"Brokerage & Investment Banking": {
"us": {
"n": 32,
"beta": 1.1715,
"de": 1.3557,
"tax": 0.1527,
"ubeta": 0.6794,
"wacc": 0.0608,
"ke": 0.0917,
"margin": -0.0,
"netm": 0.1445,
"roe": 0.1777,
"roc": None
},
"gl": {
"n": 623,
"beta": 0.9846,
"de": 1.7914,
"tax": 0.1537,
"ubeta": 0.4896,
"wacc": 0.0617,
"ke": 0.0949,
"margin": 0.0094,
"netm": 0.1524,
"roe": 0.1262,
"roc": None
}
},
"Building Materials": {
"us": {
"n": 41,
"beta": 1.1115,
"de": 0.26,
"tax": 0.1802,
"ubeta": 0.9605,
"wacc": 0.0785,
"ke": 0.0891,
"margin": 0.1264,
"netm": 0.0742,
"roe": 0.16,
"roc": 0.2016
},
"gl": {
"n": 469,
"beta": 1.0048,
"de": 0.2278,
"tax": 0.1672,
"ubeta": 0.9027,
"wacc": 0.0863,
"ke": 0.0961,
"margin": 0.104,
"netm": 0.0653,
"roe": 0.12,
"roc": 0.1419
}
},
"Business & Consumer Services": {
"us": {
"n": 155,
"beta": 0.888,
"de": 0.1972,
"tax": 0.1038,
"ubeta": 0.806,
"wacc": 0.0723,
"ke": 0.0791,
"margin": 0.1227,
"netm": 0.0703,
"roe": 0.182,
"roc": 0.283
},
"gl": {
"n": 994,
"beta": 0.9921,
"de": 0.2061,
"tax": 0.1582,
"ubeta": 0.9083,
"wacc": 0.0864,
"ke": 0.0954,
"margin": 0.1015,
"netm": 0.0583,
"roe": 0.1527,
"roc": 0.2209
}
},
"Cable TV": {
"us": {
"n": 9,
"beta": 0.7407,
"de": 1.4694,
"tax": 0.1064,
"ubeta": 0.3629,
"wacc": 0.052,
"ke": 0.0725,
"margin": 0.1849,
"netm": 0.0708,
"roe": 0.1106,
"roc": 0.1206
},
"gl": {
"n": 42,
"beta": 1.097,
"de": 1.2417,
"tax": 0.1002,
"ubeta": 0.5908,
"wacc": 0.0691,
"ke": 0.1013,
"margin": 0.1734,
"netm": 0.057,
"roe": 0.0812,
"roc": 0.1115
}
},
"Chemical (Basic)": {
"us": {
"n": 29,
"beta": 1.0122,
"de": 0.9935,
"tax": 0.0768,
"ubeta": 0.6368,
"wacc": 0.0622,
"ke": 0.0846,
"margin": 0.0267,
"netm": -0.0373,
"roe": -0.0829,
"roc": 0.0372
},
"gl": {
"n": 909,
"beta": 1.256,
"de": 0.5048,
"tax": 0.1472,
"ubeta": 1.0021,
"wacc": 0.0877,
"ke": 0.1102,
"margin": 0.0368,
"netm": -0.0036,
"roe": -0.0056,
"roc": 0.0315
}
},
"Chemical (Diversified)": {
"us": {
"n": 4,
"beta": 0.8507,
"de": 1.7611,
"tax": 0.0,
"ubeta": 0.4061,
"wacc": 0.0523,
"ke": 0.0774,
"margin": 0.0329,
"netm": -0.0535,
"roe": -0.153,
"roc": 0.0405
},
"gl": {
"n": 63,
"beta": 1.1692,
"de": 0.5252,
"tax": 0.2113,
"ubeta": 0.9101,
"wacc": 0.0831,
"ke": 0.1053,
"margin": 0.0683,
"netm": 0.0266,
"roe": 0.0461,
"roc": 0.0639
}
},
"Chemical (Specialty)": {
"us": {
"n": 59,
"beta": 0.9698,
"de": 0.2988,
"tax": 0.1368,
"ubeta": 0.8245,
"wacc": 0.0725,
"ke": 0.0828,
"margin": 0.1217,
"netm": 0.0291,
"roe": 0.035,
"roc": 0.1095
},
"gl": {
"n": 952,
"beta": 1.1536,
"de": 0.2352,
"tax": 0.1573,
"ubeta": 1.0428,
"wacc": 0.0928,
"ke": 0.1044,
"margin": 0.1097,
"netm": 0.0638,
"roe": 0.0775,
"roc": 0.0951
}
},
"Coal & Related Energy": {
"us": {
"n": 16,
"beta": 1.071,
"de": 0.0714,
"tax": 0.0312,
"ubeta": 1.1824,
"wacc": 0.0841,
"ke": 0.0873,
"margin": -0.0402,
"netm": -0.0213,
"roe": -0.0251,
"roc": -0.0476
},
"gl": {
"n": 212,
"beta": 1.1429,
"de": 0.199,
"tax": 0.1066,
"ubeta": 1.133,
"wacc": 0.0941,
"ke": 0.1038,
"margin": 0.1604,
"netm": 0.1057,
"roe": 0.1064,
"roc": 0.1415
}
},
"Computer Services": {
"us": {
"n": 64,
"beta": 1.0879,
"de": 0.251,
"tax": 0.1053,
"ubeta": 0.9617,
"wacc": 0.0783,
"ke": 0.088,
"margin": 0.0741,
"netm": 0.0445,
"roe": 0.1825,
"roc": 0.2635
},
"gl": {
"n": 1225,
"beta": 1.1167,
"de": 0.1501,
"tax": 0.1658,
"ubeta": 1.0716,
"wacc": 0.0946,
"ke": 0.1024,
"margin": 0.0756,
"netm": 0.0532,
"roe": 0.1712,
"roc": 0.2096
}
},
"Computers/Peripherals": {
"us": {
"n": 36,
"beta": 1.3503,
"de": 0.0462,
"tax": 0.0591,
"ubeta": 1.3246,
"wacc": 0.0971,
"ke": 0.0997,
"margin": 0.2248,
"netm": 0.1778,
"roe": -0.0017,
"roc": 0.4476
},
"gl": {
"n": 343,
"beta": 1.4861,
"de": 0.0619,
"tax": 0.1293,
"ubeta": 1.4682,
"wacc": 0.1185,
"ke": 0.1232,
"margin": 0.1261,
"netm": 0.1022,
"roe": 0.277,
"roc": 0.1991
}
},
"Construction Supplies": {
"us": {
"n": 40,
"beta": 1.1504,
"de": 0.1762,
"tax": 0.1604,
"ubeta": 1.0468,
"wacc": 0.0829,
"ke": 0.0908,
"margin": 0.1523,
"netm": 0.1078,
"roe": 0.2286,
"roc": 0.1671
},
"gl": {
"n": 804,
"beta": 1.0344,
"de": 0.3027,
"tax": 0.1672,
"ubeta": 0.9167,
"wacc": 0.0851,
"ke": 0.0977,
"margin": 0.0971,
"netm": 0.0774,
"roe": 0.1231,
"roc": 0.0929
}
},
"Diversified": {
"us": {
"n": 20,
"beta": 0.881,
"de": 0.1555,
"tax": 0.0276,
"ubeta": 0.8431,
"wacc": 0.073,
"ke": 0.0788,
"margin": 0.2273,
"netm": 0.1637,
"roe": 0.1137,
"roc": 0.1482
},
"gl": {
"n": 329,
"beta": 0.7974,
"de": 0.485,
"tax": 0.1518,
"ubeta": 0.6526,
"wacc": 0.0709,
"ke": 0.0844,
"margin": 0.1511,
"netm": 0.0892,
"roe": 0.0894,
"roc": 0.0898
}
},
"Drugs (Biotechnology)": {
"us": {
"n": 496,
"beta": 1.1353,
"de": 0.1304,
"tax": 0.0108,
"ubeta": 1.0795,
"wacc": 0.0849,
"ke": 0.0901,
"margin": 0.0897,
"netm": -0.05,
"roe": -0.0567,
"roc": 0.0353
},
"gl": {
"n": 1193,
"beta": 1.2308,
"de": 0.1235,
"tax": 0.0208,
"ubeta": 1.1808,
"wacc": 0.1024,
"ke": 0.1088,
"margin": 0.0748,
"netm": -0.0369,
"roe": -0.0324,
"roc": 0.0299
}
},
"Drugs (Pharmaceutical)": {
"us": {
"n": 228,
"beta": 0.9828,
"de": 0.1454,
"tax": 0.0299,
"ubeta": 0.9151,
"wacc": 0.0785,
"ke": 0.0833,
"margin": 0.2954,
"netm": 0.1854,
"roe": 0.2404,
"roc": 0.1695
},
"gl": {
"n": 1260,
"beta": 1.0626,
"de": 0.1494,
"tax": 0.1035,
"ubeta": 0.9988,
"wacc": 0.0922,
"ke": 0.0993,
"margin": 0.2307,
"netm": 0.1449,
"roe": 0.1677,
"roc": 0.1474
}
},
"Education": {
"us": {
"n": 32,
"beta": 0.7809,
"de": 0.2438,
"tax": 0.1554,
"ubeta": 0.7196,
"wacc": 0.0675,
"ke": 0.0743,
"margin": 0.1401,
"netm": 0.0879,
"roe": 0.159,
"roc": 0.1594
},
"gl": {
"n": 281,
"beta": 0.8117,
"de": 0.2861,
"tax": 0.1455,
"ubeta": 0.7446,
"wacc": 0.0759,
"ke": 0.0852,
"margin": 0.1593,
"netm": 0.102,
"roe": 0.1231,
"roc": 0.1436
}
},
"Electrical Equipment": {
"us": {
"n": 112,
"beta": 1.2511,
"de": 0.12,
"tax": 0.0482,
"ubeta": 1.1898,
"wacc": 0.0899,
"ke": 0.0953,
"margin": 0.0953,
"netm": 0.0094,
"roe": 0.0153,
"roc": 0.156
},
"gl": {
"n": 1158,
"beta": 1.3735,
"de": 0.1374,
"tax": 0.122,
"ubeta": 1.3406,
"wacc": 0.1081,
"ke": 0.1168,
"margin": 0.0835,
"netm": 0.0538,
"roe": 0.0962,
"roc": 0.1145
}
},
"Electronics (Consumer & Office)": {
"us": {
"n": 8,
"beta": 0.866,
"de": 0.058,
"tax": 0.0,
"ubeta": 0.9274,
"wacc": 0.0763,
"ke": 0.0781,
"margin": -0.0449,
"netm": -0.0942,
"roe": -0.2881,
"roc": -0.0835
},
"gl": {
"n": 122,
"beta": 1.1971,
"de": 0.1633,
"tax": 0.1328,
"ubeta": 1.1926,
"wacc": 0.098,
"ke": 0.1069,
"margin": 0.0602,
"netm": 0.0433,
"roe": 0.096,
"roc": 0.0807
}
},
"Electronics (General)": {
"us": {
"n": 114,
"beta": 0.9715,
"de": 0.1101,
"tax": 0.0804,
"ubeta": 0.9375,
"wacc": 0.0785,
"ke": 0.0828,
"margin": 0.1042,
"netm": 0.0647,
"roe": 0.1262,
"roc": 0.1791
},
"gl": {
"n": 1481,
"beta": 1.5982,
"de": 0.1417,
"tax": 0.1189,
"ubeta": 1.5685,
"wacc": 0.1188,
"ke": 0.1295,
"margin": 0.0629,
"netm": 0.049,
"roe": 0.0883,
"roc": 0.0824
}
},
"Engineering/Construction": {
"us": {
"n": 48,
"beta": 1.21,
"de": 0.1401,
"tax": 0.1364,
"ubeta": 1.1374,
"wacc": 0.0869,
"ke": 0.0935,
"margin": 0.0649,
"netm": 0.0594,
"roe": 0.2614,
"roc": 0.2532
},
"gl": {
"n": 1390,
"beta": 1.001,
"de": 0.7655,
"tax": 0.1766,
"ubeta": 0.7593,
"wacc": 0.073,
"ke": 0.0959,
"margin": 0.051,
"netm": 0.0335,
"roe": 0.1038,
"roc": 0.0719
}
},
"Entertainment": {
"us": {
"n": 92,
"beta": 0.8252,
"de": 0.1591,
"tax": 0.033,
"ubeta": 0.7628,
"wacc": 0.0713,
"ke": 0.0763,
"margin": 0.106,
"netm": 0.0443,
"roe": 0.0609,
"roc": 0.1242
},
"gl": {
"n": 733,
"beta": 1.0127,
"de": 0.1273,
"tax": 0.0803,
"ubeta": 0.9821,
"wacc": 0.0907,
"ke": 0.0965,
"margin": 0.1164,
"netm": 0.052,
"roe": 0.0568,
"roc": 0.1104
}
},
"Environmental & Waste Services": {
"us": {
"n": 53,
"beta": 0.9455,
"de": 0.2145,
"tax": 0.0427,
"ubeta": 0.8248,
"wacc": 0.0743,
"ke": 0.0817,
"margin": 0.1461,
"netm": 0.0824,
"roe": 0.1974,
"roc": 0.3175
},
"gl": {
"n": 397,
"beta": 1.1018,
"de": 0.357,
"tax": 0.128,
"ubeta": 0.908,
"wacc": 0.0862,
"ke": 0.1015,
"margin": 0.1127,
"netm": 0.0638,
"roe": 0.1015,
"roc": 0.1041
}
},
"Farming/Agriculture": {
"us": {
"n": 35,
"beta": 1.1292,
"de": 0.5185,
"tax": 0.0629,
"ubeta": 0.8458,
"wacc": 0.0727,
"ke": 0.0899,
"margin": 0.0545,
"netm": 0.0391,
"roe": 0.1204,
"roc": 0.0728
},
"gl": {
"n": 428,
"beta": 0.6699,
"de": 0.5904,
"tax": 0.1563,
"ubeta": 0.4927,
"wacc": 0.0646,
"ke": 0.0772,
"margin": 0.0639,
"netm": 0.041,
"roe": 0.0983,
"roc": 0.0678
}
},
"Financial Svcs. (Non-bank & Insurance)": {
"us": {
"n": 176,
"beta": 0.9697,
"de": 2.7213,
"tax": 0.1206,
"ubeta": 0.3277,
"wacc": 0.05,
"ke": 0.0827,
"margin": 0.1848,
"netm": 0.2219,
"roe": 0.2882,
"roc": None
},
"gl": {
"n": 1138,
"beta": 0.8235,
"de": 2.6481,
"tax": 0.1591,
"ubeta": 0.2951,
"wacc": 0.0549,
"ke": 0.0859,
"margin": 0.1413,
"netm": 0.2338,
"roe": 0.1883,
"roc": None
}
},
"Food Processing": {
"us": {
"n": 78,
"beta": 0.6075,
"de": 0.4373,
"tax": 0.1037,
"ubeta": 0.4694,
"wacc": 0.0579,
"ke": 0.0666,
"margin": 0.1063,
"netm": 0.0282,
"roe": 0.046,
"roc": 0.1595
},
"gl": {
"n": 1450,
"beta": 0.6737,
"de": 0.371,
"tax": 0.1635,
"ubeta": 0.5602,
"wacc": 0.0682,
"ke": 0.0774,
"margin": 0.0854,
"netm": 0.0465,
"roe": 0.1054,
"roc": 0.1197
}
},
"Food Wholesalers": {
"us": {
"n": 13,
"beta": 0.8666,
"de": 0.4697,
"tax": 0.0915,
"ubeta": 0.6478,
"wacc": 0.0653,
"ke": 0.0782,
"margin": 0.0261,
"netm": 0.0117,
"roe": 0.1822,
"roc": 0.1784
},
"gl": {
"n": 183,
"beta": 0.6848,
"de": 0.5824,
"tax": 0.1744,
"ubeta": 0.4989,
"wacc": 0.0652,
"ke": 0.0781,
"margin": 0.0254,
"netm": 0.0101,
"roe": 0.0974,
"roc": 0.1067
}
},
"Furn/Home Furnishings": {
"us": {
"n": 27,
"beta": 0.8232,
"de": 0.4233,
"tax": 0.1138,
"ubeta": 0.6521,
"wacc": 0.0653,
"ke": 0.0762,
"margin": 0.0659,
"netm": 0.011,
"roe": 0.0311,
"roc": 0.1059
},
"gl": {
"n": 383,
"beta": 0.9675,
"de": 0.2573,
"tax": 0.1539,
"ubeta": 0.9384,
"wacc": 0.0836,
"ke": 0.094,
"margin": 0.0765,
"netm": 0.0563,
"roe": 0.1249,
"roc": 0.1261
}
},
"Green & Renewable Energy": {
"us": {
"n": 15,
"beta": 0.8563,
"de": 1.1311,
"tax": 0.0,
"ubeta": 0.4723,
"wacc": 0.0604,
"ke": 0.0777,
"margin": 0.1987,
"netm": -0.1083,
"roe": -0.0736,
"roc": 0.0364
},
"gl": {
"n": 258,
"beta": 0.8367,
"de": 0.7143,
"tax": 0.11,
"ubeta": 0.5668,
"wacc": 0.0685,
"ke": 0.0866,
"margin": 0.2772,
"netm": 0.1086,
"roe": 0.0558,
"roc": 0.0549
}
},
"Healthcare Products": {
"us": {
"n": 204,
"beta": 0.9086,
"de": 0.1279,
"tax": 0.0485,
"ubeta": 0.8569,
"wacc": 0.0754,
"ke": 0.08,
"margin": 0.1534,
"netm": 0.0961,
"roe": 0.1126,
"roc": 0.1698
},
"gl": {
"n": 842,
"beta": 1.182,
"de": 0.1386,
"tax": 0.0845,
"ubeta": 1.1165,
"wacc": 0.0986,
"ke": 0.106,
"margin": 0.1427,
"netm": 0.0875,
"roe": 0.0906,
"roc": 0.137
}
},
"Healthcare Support Services": {
"us": {
"n": 104,
"beta": 0.872,
"de": 0.3543,
"tax": 0.098,
"ubeta": 0.7449,
"wacc": 0.0683,
"ke": 0.0784,
"margin": 0.03,
"netm": 0.0125,
"roe": 0.0989,
"roc": 0.3119
},
"gl": {
"n": 478,
"beta": 0.9166,
"de": 0.3813,
"tax": 0.1462,
"ubeta": 0.7787,
"wacc": 0.0779,
"ke": 0.0911,
"margin": 0.031,
"netm": 0.0134,
"roe": 0.0849,
"roc": 0.2072
}
},
"Heathcare Information and Technology": {
"us": {
"n": 115,
"beta": 1.1083,
"de": 0.1574,
"tax": 0.0638,
"ubeta": 1.0163,
"wacc": 0.0822,
"ke": 0.0889,
"margin": 0.1471,
"netm": 0.0745,
"roe": 0.064,
"roc": 0.1372
},
"gl": {
"n": 430,
"beta": 1.2899,
"de": 0.1396,
"tax": 0.0786,
"ubeta": 1.2072,
"wacc": 0.1039,
"ke": 0.1121,
"margin": 0.1479,
"netm": 0.0948,
"roe": 0.0793,
"roc": 0.1254
}
},
"Homebuilding": {
"us": {
"n": 30,
"beta": 0.9106,
"de": 0.2134,
"tax": 0.1699,
"ubeta": 0.8532,
"wacc": 0.0727,
"ke": 0.0801,
"margin": 0.1257,
"netm": 0.0947,
"roe": 0.1423,
"roc": 0.1491
},
"gl": {
"n": 160,
"beta": 0.9602,
"de": 0.399,
"tax": 0.1973,
"ubeta": 0.8224,
"wacc": 0.0792,
"ke": 0.0936,
"margin": 0.1071,
"netm": 0.073,
"roe": 0.1147,
"roc": 0.1036
}
},
"Hospitals/Healthcare Facilities": {
"us": {
"n": 31,
"beta": 0.7997,
"de": 0.5992,
"tax": 0.1135,
"ubeta": 0.5649,
"wacc": 0.0619,
"ke": 0.0752,
"margin": 0.1336,
"netm": 0.063,
"roe": 0.5084,
"roc": 0.2216
},
"gl": {
"n": 249,
"beta": 0.7602,
"de": 0.4658,
"tax": 0.1846,
"ubeta": 0.5839,
"wacc": 0.0699,
"ke": 0.0823,
"margin": 0.1227,
"netm": 0.0599,
"roe": 0.1764,
"roc": 0.1321
}
},
"Hotel/Gaming": {
"us": {
"n": 63,
"beta": 1.0804,
"de": 0.3975,
"tax": 0.0831,
"ubeta": 0.8757,
"wacc": 0.0736,
"ke": 0.0877,
"margin": 0.1939,
"netm": 0.1038,
"roe": 0.4538,
"roc": 0.1458
},
"gl": {
"n": 656,
"beta": 0.7984,
"de": 0.4024,
"tax": 0.1506,
"ubeta": 0.6562,
"wacc": 0.0726,
"ke": 0.0845,
"margin": 0.1666,
"netm": 0.092,
"roe": 0.1895,
"roc": 0.118
}
},
"Household Products": {
"us": {
"n": 110,
"beta": 0.8155,
"de": 0.1815,
"tax": 0.065,
"ubeta": 0.7411,
"wacc": 0.0703,
"ke": 0.0759,
"margin": 0.1862,
"netm": 0.1168,
"roe": 0.2702,
"roc": 0.3442
},
"gl": {
"n": 588,
"beta": 0.8301,
"de": 0.1567,
"tax": 0.1311,
"ubeta": 0.7741,
"wacc": 0.0804,
"ke": 0.0862,
"margin": 0.1617,
"netm": 0.0946,
"roe": 0.1801,
"roc": 0.2308
}
},
"Information Services": {
"us": {
"n": 15,
"beta": 0.9206,
"de": 0.3317,
"tax": 0.1816,
"ubeta": 0.7564,
"wacc": 0.07,
"ke": 0.0806,
"margin": 0.1189,
"netm": 0.0653,
"roe": 0.1495,
"roc": 0.2217
},
"gl": {
"n": 86,
"beta": 1.0237,
"de": 0.3198,
"tax": 0.1982,
"ubeta": 0.8737,
"wacc": 0.0841,
"ke": 0.0971,
"margin": 0.1178,
"netm": 0.0635,
"roe": 0.1455,
"roc": 0.2281
}
},
"Insurance (General)": {
"us": {
"n": 21,
"beta": 0.672,
"de": 0.2563,
"tax": 0.1277,
"ubeta": 0.5781,
"wacc": 0.0634,
"ke": 0.0695,
"margin": 0.2131,
"netm": 0.1237,
"roe": 0.1907,
"roc": 0.4451
},
"gl": {
"n": 204,
"beta": 0.5102,
"de": 0.3006,
"tax": 0.1538,
"ubeta": 0.4731,
"wacc": 0.0624,
"ke": 0.0682,
"margin": 0.1545,
"netm": 0.089,
"roe": 0.1853,
"roc": 0.2562
}
},
"Insurance (Life)": {
"us": {
"n": 20,
"beta": 0.6445,
"de": 0.6784,
"tax": 0.1519,
"ubeta": 0.5317,
"wacc": 0.056,
"ke": 0.0682,
"margin": 0.1061,
"netm": 0.078,
"roe": 0.1287,
"roc": 0.1077
},
"gl": {
"n": 143,
"beta": 0.8038,
"de": 0.7513,
"tax": 0.1725,
"ubeta": 0.7948,
"wacc": 0.0669,
"ke": 0.0848,
"margin": 0.1729,
"netm": 0.1022,
"roe": 0.1415,
"roc": 0.1448
}
},
"Insurance (Prop/Cas.)": {
"us": {
"n": 57,
"beta": 0.4841,
"de": 0.1483,
"tax": 0.1837,
"ubeta": 0.457,
"wacc": 0.0578,
"ke": 0.0611,
"margin": 0.1525,
"netm": 0.1113,
"roe": 0.1871,
"roc": 0.1849
},
"gl": {
"n": 248,
"beta": 0.4318,
"de": 0.1634,
"tax": 0.1938,
"ubeta": 0.4124,
"wacc": 0.0606,
"ke": 0.0638,
"margin": 0.1526,
"netm": 0.1082,
"roe": 0.1715,
"roc": 0.1805
}
},
"Investments & Asset Management": {
"us": {
"n": 283,
"beta": 0.6596,
"de": 0.3269,
"tax": 0.0353,
"ubeta": 0.5881,
"wacc": 0.0613,
"ke": 0.0689,
"margin": 0.255,
"netm": 0.1836,
"roe": 0.1588,
"roc": 0.1425
},
"gl": {
"n": 1315,
"beta": 0.7483,
"de": 0.6034,
"tax": 0.0728,
"ubeta": 0.5657,
"wacc": 0.0672,
"ke": 0.0816,
"margin": 0.2505,
"netm": 0.1715,
"roe": 0.1201,
"roc": 0.083
}
},
"Machinery": {
"us": {
"n": 105,
"beta": 0.9636,
"de": 0.1469,
"tax": 0.1337,
"ubeta": 0.894,
"wacc": 0.077,
"ke": 0.0825,
"margin": 0.1586,
"netm": 0.1058,
"roe": 0.1642,
"roc": 0.2441
},
"gl": {
"n": 1553,
"beta": 1.3695,
"de": 0.1356,
"tax": 0.1599,
"ubeta": 1.3296,
"wacc": 0.1078,
"ke": 0.1166,
"margin": 0.1036,
"netm": 0.073,
"roe": 0.109,
"roc": 0.1184
}
},
"Metals & Mining": {
"us": {
"n": 73,
"beta": 1.043,
"de": 0.1098,
"tax": 0.0252,
"ubeta": 1.0104,
"wacc": 0.082,
"ke": 0.086,
"margin": 0.2385,
"netm": 0.1052,
"roe": 0.1779,
"roc": 0.2704
},
"gl": {
"n": 1874,
"beta": 1.2363,
"de": 0.2304,
"tax": 0.0437,
"ubeta": 1.1256,
"wacc": 0.0981,
"ke": 0.1091,
"margin": 0.1073,
"netm": 0.0483,
"roe": 0.0913,
"roc": 0.1366
}
},
"Office Equipment & Services": {
"us": {
"n": 14,
"beta": 1.3344,
"de": 0.481,
"tax": 0.123,
"ubeta": 1.0382,
"wacc": 0.0792,
"ke": 0.099,
"margin": 0.1073,
"netm": 0.0438,
"roe": 0.1323,
"roc": 0.1826
},
"gl": {
"n": 139,
"beta": 0.7587,
"de": 0.2857,
"tax": 0.1619,
"ubeta": 0.7113,
"wacc": 0.0735,
"ke": 0.0822,
"margin": 0.0773,
"netm": 0.0443,
"roe": 0.0874,
"roc": 0.1262
}
},
"Oil/Gas (Integrated)": {
"us": {
"n": 4,
"beta": 0.2994,
"de": 0.1385,
"tax": 0.2824,
"ubeta": 0.278,
"wacc": 0.0507,
"ke": 0.0529,
"margin": 0.1125,
"netm": 0.083,
"roe": 0.0996,
"roc": 0.0845
},
"gl": {
"n": 34,
"beta": 0.6887,
"de": 0.216,
"tax": 0.2827,
"ubeta": 0.6325,
"wacc": 0.0716,
"ke": 0.0783,
"margin": 0.1427,
"netm": 0.0748,
"roe": 0.1221,
"roc": 0.1388
}
},
"Oil/Gas (Production and Exploration)": {
"us": {
"n": 142,
"beta": 0.7214,
"de": 0.3759,
"tax": 0.0666,
"ubeta": 0.5785,
"wacc": 0.0625,
"ke": 0.0717,
"margin": 0.2542,
"netm": 0.1463,
"roe": 0.1221,
"roc": 0.1373
},
"gl": {
"n": 539,
"beta": 0.8856,
"de": 0.3582,
"tax": 0.0896,
"ubeta": 0.7464,
"wacc": 0.0776,
"ke": 0.0894,
"margin": 0.2851,
"netm": 0.1572,
"roe": 0.118,
"roc": 0.1487
}
},
"Oil/Gas Distribution": {
"us": {
"n": 23,
"beta": 0.6692,
"de": 0.5853,
"tax": 0.0917,
"ubeta": 0.4693,
"wacc": 0.0578,
"ke": 0.0693,
"margin": 0.2578,
"netm": 0.1335,
"roe": 0.1803,
"roc": 0.1235
},
"gl": {
"n": 186,
"beta": 0.6535,
"de": 0.6154,
"tax": 0.1214,
"ubeta": 0.4612,
"wacc": 0.0637,
"ke": 0.0763,
"margin": 0.1724,
"netm": 0.1006,
"roe": 0.1305,
"roc": 0.0919
}
},
"Oilfield Svcs/Equip.": {
"us": {
"n": 97,
"beta": 0.9512,
"de": 0.3736,
"tax": 0.0875,
"ubeta": 0.7871,
"wacc": 0.0704,
"ke": 0.0819,
"margin": 0.0465,
"netm": 0.0234,
"roe": 0.0865,
"roc": 0.1194
},
"gl": {
"n": 431,
"beta": 0.9482,
"de": 0.3966,
"tax": 0.1373,
"ubeta": 0.7997,
"wacc": 0.0788,
"ke": 0.0929,
"margin": 0.0501,
"netm": 0.028,
"roe": 0.0826,
"roc": 0.0906
}
},
"Packaging & Container": {
"us": {
"n": 19,
"beta": 1.0219,
"de": 0.5511,
"tax": 0.1557,
"ubeta": 0.749,
"wacc": 0.0675,
"ke": 0.0851,
"margin": 0.0958,
"netm": 0.0448,
"roe": 0.1229,
"roc": 0.1482
},
"gl": {
"n": 438,
"beta": 0.7591,
"de": 0.5265,
"tax": 0.1667,
"ubeta": 0.5756,
"wacc": 0.0688,
"ke": 0.0822,
"margin": 0.0784,
"netm": 0.0429,
"roe": 0.0858,
"roc": 0.0928
}
},
"Paper/Forest Products": {
"us": {
"n": 6,
"beta": 0.958,
"de": 0.4369,
"tax": 0.086,
"ubeta": 0.7697,
"wacc": 0.0693,
"ke": 0.0822,
"margin": 0.0634,
"netm": 0.0344,
"roe": 0.0701,
"roc": 0.1041
},
"gl": {
"n": 271,
"beta": 0.8887,
"de": 0.7808,
"tax": 0.1251,
"ubeta": 0.6107,
"wacc": 0.0692,
"ke": 0.0895,
"margin": 0.043,
"netm": 0.0147,
"roe": 0.0176,
"roc": 0.0291
}
},
"Power": {
"us": {
"n": 46,
"beta": 0.4824,
"de": 0.7415,
"tax": 0.1275,
"ubeta": 0.3146,
"wacc": 0.0501,
"ke": 0.061,
"margin": 0.2147,
"netm": 0.1273,
"roe": 0.124,
"roc": 0.0692
},
"gl": {
"n": 486,
"beta": 0.7131,
"de": 0.8587,
"tax": 0.1786,
"ubeta": 0.4553,
"wacc": 0.0628,
"ke": 0.0796,
"margin": 0.1516,
"netm": 0.0822,
"roe": 0.1027,
"roc": 0.0702
}
},
"Precious Metals": {
"us": {
"n": 56,
"beta": 0.8366,
"de": 0.0728,
"tax": 0.0597,
"ubeta": 0.8309,
"wacc": 0.0747,
"ke": 0.0768,
"margin": 0.4039,
"netm": 0.2859,
"roe": 0.2352,
"roc": 0.2545
},
"gl": {
"n": 777,
"beta": 1.3975,
"de": 0.0906,
"tax": 0.0511,
"ubeta": 1.3739,
"wacc": 0.1125,
"ke": 0.1182,
"margin": 0.2494,
"netm": 0.1515,
"roe": 0.169,
"roc": 0.2153
}
},
"Publishing & Newspapers": {
"us": {
"n": 19,
"beta": 0.563,
"de": 0.2394,
"tax": 0.1021,
"ubeta": 0.5119,
"wacc": 0.0595,
"ke": 0.0646,
"margin": 0.0998,
"netm": 0.0819,
"roe": 0.1383,
"roc": 0.1763
},
"gl": {
"n": 307,
"beta": 0.8166,
"de": 0.2799,
"tax": 0.1503,
"ubeta": 0.7788,
"wacc": 0.0762,
"ke": 0.0855,
"margin": 0.0738,
"netm": 0.0497,
"roe": 0.0703,
"roc": 0.0932
}
},
"R.E.I.T.": {
"us": {
"n": 190,
"beta": 0.6418,
"de": 0.8446,
"tax": 0.0158,
"ubeta": 0.4005,
"wacc": 0.0532,
"ke": 0.0681,
"margin": 0.2464,
"netm": 0.1323,
"roe": 0.0504,
"roc": 0.032
},
"gl": {
"n": 643,
"beta": 0.5649,
"de": 0.8007,
"tax": 0.0397,
"ubeta": 0.3617,
"wacc": 0.0577,
"ke": 0.0713,
"margin": 0.3192,
"netm": 0.1953,
"roe": 0.0532,
"roc": 0.0366
}
},
"Real Estate (Development)": {
"us": {
"n": 14,
"beta": 0.8436,
"de": 1.0183,
"tax": 0.0491,
"ubeta": 0.5641,
"wacc": 0.0582,
"ke": 0.0771,
"margin": 0.2153,
"netm": 0.0701,
"roe": 0.0506,
"roc": 0.0704
},
"gl": {
"n": 895,
"beta": 0.9256,
"de": 1.9118,
"tax": 0.1452,
"ubeta": 0.4459,
"wacc": 0.0598,
"ke": 0.0916,
"margin": 0.0346,
"netm": -0.0694,
"roe": -0.0592,
"roc": 0.0121
}
},
"Real Estate (General/Diversified)": {
"us": {
"n": 12,
"beta": 0.81,
"de": 0.5356,
"tax": 0.0465,
"ubeta": 0.627,
"wacc": 0.0625,
"ke": 0.0756,
"margin": 0.2145,
"netm": 0.2377,
"roe": 0.1077,
"roc": 0.0519
},
"gl": {
"n": 312,
"beta": 0.9279,
"de": 0.8856,
"tax": 0.1429,
"ubeta": 0.5976,
"wacc": 0.0689,
"ke": 0.0917,
"margin": 0.1492,
"netm": 0.0721,
"roe": 0.0344,
"roc": 0.0359
}
},
"Real Estate (Operations & Services)": {
"us": {
"n": 54,
"beta": 0.9655,
"de": 0.2464,
"tax": 0.087,
"ubeta": 0.8576,
"wacc": 0.0741,
"ke": 0.0826,
"margin": 0.0285,
"netm": 0.0119,
"roe": 0.033,
"roc": 0.0594
},
"gl": {
"n": 752,
"beta": 0.7818,
"de": 0.825,
"tax": 0.1427,
"ubeta": 0.5141,
"wacc": 0.0653,
"ke": 0.0835,
"margin": 0.174,
"netm": 0.1057,
"roe": 0.0502,
"roc": 0.0419
}
},
"Recreation": {
"us": {
"n": 49,
"beta": 1.0235,
"de": 0.6299,
"tax": 0.1145,
"ubeta": 0.7365,
"wacc": 0.0676,
"ke": 0.0851,
"margin": 0.0969,
"netm": -0.0472,
"roe": -0.1276,
"roc": 0.0802
},
"gl": {
"n": 332,
"beta": 1.0064,
"de": 0.3337,
"tax": 0.1477,
"ubeta": 0.89,
"wacc": 0.0829,
"ke": 0.0962,
"margin": 0.1052,
"netm": 0.0246,
"roe": 0.0389,
"roc": 0.0953
}
},
"Reinsurance": {
"us": {
"n": 1,
"beta": 0.5813,
"de": 0.4347,
"tax": 0.3036,
"ubeta": 0.5777,
"wacc": 0.0564,
"ke": 0.0654,
"margin": 0.0721,
"netm": 0.0389,
"roe": 0.0779,
"roc": 0.1014
},
"gl": {
"n": 32,
"beta": 0.9895,
"de": 0.2028,
"tax": 0.1774,
"ubeta": 0.9527,
"wacc": 0.0864,
"ke": 0.0952,
"margin": 0.1332,
"netm": 0.0916,
"roe": 0.1565,
"roc": 0.1745
}
},
"Restaurant/Dining": {
"us": {
"n": 64,
"beta": 0.9241,
"de": 0.2722,
"tax": 0.0992,
"ubeta": 0.783,
"wacc": 0.0716,
"ke": 0.0807,
"margin": 0.1579,
"netm": 0.0937,
"roe": 0.001,
"roc": 0.1836
},
"gl": {
"n": 410,
"beta": 0.7547,
"de": 0.2601,
"tax": 0.1521,
"ubeta": 0.6606,
"wacc": 0.074,
"ke": 0.082,
"margin": 0.0951,
"netm": 0.0541,
"roe": 0.2814,
"roc": 0.1418
}
},
"Retail (Automotive)": {
"us": {
"n": 34,
"beta": 0.936,
"de": 0.4536,
"tax": 0.1077,
"ubeta": 0.7132,
"wacc": 0.0678,
"ke": 0.0812,
"margin": 0.0624,
"netm": 0.0336,
"roe": 0.3438,
"roc": 0.1219
},
"gl": {
"n": 212,
"beta": 0.8346,
"de": 0.5275,
"tax": 0.1693,
"ubeta": 0.6298,
"wacc": 0.0715,
"ke": 0.0865,
"margin": 0.0515,
"netm": 0.0208,
"roe": 0.1272,
"roc": 0.1047
}
},
"Retail (Building Supply)": {
"us": {
"n": 14,
"beta": 1.5353,
"de": 0.2329,
"tax": 0.1184,
"ubeta": 1.3177,
"wacc": 0.0951,
"ke": 0.108,
"margin": 0.1194,
"netm": 0.0784,
"roe": None,
"roc": 0.3495
},
"gl": {
"n": 121,
"beta": 0.9449,
"de": 0.2595,
"tax": 0.1844,
"ubeta": 0.8047,
"wacc": 0.0825,
"ke": 0.0927,
"margin": 0.1059,
"netm": 0.0649,
"roe": 0.7078,
"roc": 0.2314
}
},
"Retail (Distributors)": {
"us": {
"n": 62,
"beta": 0.9484,
"de": 0.2824,
"tax": 0.1459,
"ubeta": 0.8016,
"wacc": 0.0722,
"ke": 0.0818,
"margin": 0.101,
"netm": 0.0605,
"roe": 0.1833,
"roc": 0.1611
},
"gl": {
"n": 1079,
"beta": 0.8136,
"de": 0.4834,
"tax": 0.1748,
"ubeta": 0.6428,
"wacc": 0.0716,
"ke": 0.0853,
"margin": 0.0479,
"netm": 0.0379,
"roe": 0.1151,
"roc": 0.0726
}
},
"Retail (General)": {
"us": {
"n": 23,
"beta": 0.8052,
"de": 0.0794,
"tax": 0.191,
"ubeta": 0.7809,
"wacc": 0.0727,
"ke": 0.0754,
"margin": 0.068,
"netm": 0.0561,
"roe": 0.2605,
"roc": 0.1359
},
"gl": {
"n": 252,
"beta": 0.9825,
"de": 0.1304,
"tax": 0.1767,
"ubeta": 0.9373,
"wacc": 0.0889,
"ke": 0.0948,
"margin": 0.0647,
"netm": 0.055,
"roe": 0.2103,
"roc": 0.1172
}
},
"Retail (Grocery and Food)": {
"us": {
"n": 15,
"beta": 1.1183,
"de": 0.5195,
"tax": 0.1222,
"ubeta": 0.8484,
"wacc": 0.0724,
"ke": 0.0894,
"margin": 0.0229,
"netm": 0.0132,
"roe": 0.129,
"roc": 0.0676
},
"gl": {
"n": 215,
"beta": 0.8735,
"de": 0.4596,
"tax": 0.2081,
"ubeta": 0.6905,
"wacc": 0.0744,
"ke": 0.0887,
"margin": 0.0378,
"netm": 0.0194,
"roe": 0.1096,
"roc": 0.1008
}
},
"Retail (REITs)": {
"us": {
"n": 26,
"beta": 0.6207,
"de": 0.5642,
"tax": 0.016,
"ubeta": 0.4427,
"wacc": 0.0557,
"ke": 0.0672,
"margin": 0.4025,
"netm": 0.23,
"roe": 0.0636,
"roc": 0.0516
},
"gl": {
"n": 113,
"beta": 0.6078,
"de": 0.7113,
"tax": 0.0682,
"ubeta": 0.4073,
"wacc": 0.06,
"ke": 0.0737,
"margin": 0.5002,
"netm": 0.2783,
"roe": 0.0583,
"roc": 0.0509
}
},
"Retail (Special Lines)": {
"us": {
"n": 94,
"beta": 1.0894,
"de": 0.1976,
"tax": 0.1007,
"ubeta": 1.0019,
"wacc": 0.0801,
"ke": 0.0881,
"margin": 0.0773,
"netm": 0.0519,
"roe": 0.3012,
"roc": 0.2154
},
"gl": {
"n": 649,
"beta": 0.9604,
"de": 0.1836,
"tax": 0.1692,
"ubeta": 0.9036,
"wacc": 0.0858,
"ke": 0.0936,
"margin": 0.0741,
"netm": 0.0457,
"roe": 0.1657,
"roc": 0.17
}
},
"Rubber& Tires": {
"us": {
"n": 3,
"beta": 0.5294,
"de": 3.5847,
"tax": 0.0,
"ubeta": 0.1544,
"wacc": 0.0448,
"ke": 0.0631,
"margin": 0.0224,
"netm": -0.0949,
"roe": -0.3641,
"roc": 0.0317
},
"gl": {
"n": 91,
"beta": 0.9408,
"de": 0.4412,
"tax": 0.1804,
"ubeta": 0.7807,
"wacc": 0.0774,
"ke": 0.0925,
"margin": 0.073,
"netm": 0.0335,
"roe": 0.0605,
"roc": 0.0828
}
},
"Semiconductor": {
"us": {
"n": 66,
"beta": 1.5182,
"de": 0.0259,
"tax": 0.0511,
"ubeta": 1.5046,
"wacc": 0.1055,
"ke": 0.1072,
"margin": 0.3533,
"netm": 0.3045,
"roe": 0.3136,
"roc": 0.2723
},
"gl": {
"n": 675,
"beta": 1.8768,
"de": 0.0413,
"tax": 0.0846,
"ubeta": 1.8689,
"wacc": 0.1412,
"ke": 0.1452,
"margin": 0.2699,
"netm": 0.2332,
"roe": 0.2399,
"roc": 0.2054
}
},
"Semiconductor Equip": {
"us": {
"n": 31,
"beta": 1.3972,
"de": 0.0486,
"tax": 0.0996,
"ubeta": 1.3917,
"wacc": 0.0989,
"ke": 0.1018,
"margin": 0.2617,
"netm": 0.2132,
"roe": 0.3578,
"roc": 0.284
},
"gl": {
"n": 391,
"beta": 2.1258,
"de": 0.0561,
"tax": 0.1219,
"ubeta": 2.1173,
"wacc": 0.1531,
"ke": 0.1592,
"margin": 0.2028,
"netm": 0.1574,
"roe": 0.1972,
"roc": 0.1716
}
},
"Shipbuilding & Marine": {
"us": {
"n": 8,
"beta": 0.7529,
"de": 0.2255,
"tax": 0.0526,
"ubeta": 0.6608,
"wacc": 0.0669,
"ke": 0.0731,
"margin": 0.126,
"netm": 0.0948,
"roe": 0.1015,
"roc": 0.1199
},
"gl": {
"n": 359,
"beta": 0.8744,
"de": 0.4169,
"tax": 0.1506,
"ubeta": 0.7871,
"wacc": 0.0753,
"ke": 0.0887,
"margin": 0.1434,
"netm": 0.1367,
"roe": 0.114,
"roc": 0.0884
}
},
"Shoe": {
"us": {
"n": 11,
"beta": 1.0173,
"de": 0.1194,
"tax": 0.1186,
"ubeta": 1.0002,
"wacc": 0.0801,
"ke": 0.0849,
"margin": 0.0903,
"netm": 0.0627,
"roe": 0.1949,
"roc": 0.2093
},
"gl": {
"n": 84,
"beta": 0.9184,
"de": 0.1429,
"tax": 0.1507,
"ubeta": 0.8938,
"wacc": 0.0852,
"ke": 0.0912,
"margin": 0.088,
"netm": 0.0582,
"roe": 0.14,
"roc": 0.1529
}
},
"Software (Entertainment)": {
"us": {
"n": 77,
"beta": 1.0283,
"de": 0.0204,
"tax": 0.0529,
"ubeta": 1.0207,
"wacc": 0.0844,
"ke": 0.0854,
"margin": 0.3385,
"netm": 0.2993,
"roe": 0.3651,
"roc": 0.2702
},
"gl": {
"n": 298,
"beta": 1.2464,
"de": 0.0314,
"tax": 0.1087,
"ubeta": 1.2346,
"wacc": 0.1077,
"ke": 0.1097,
"margin": 0.319,
"netm": 0.2827,
"roe": 0.3098,
"roc": 0.2283
}
},
"Software (Internet)": {
"us": {
"n": 29,
"beta": 1.6887,
"de": 0.123,
"tax": 0.0305,
"ubeta": 1.5905,
"wacc": 0.1066,
"ke": 0.1148,
"margin": 0.0369,
"netm": -0.0093,
"roe": -0.0147,
"roc": 0.0343
},
"gl": {
"n": 150,
"beta": 1.3921,
"de": 0.1001,
"tax": 0.1132,
"ubeta": 1.337,
"wacc": 0.1112,
"ke": 0.1179,
"margin": 0.0617,
"netm": 0.0348,
"roe": 0.06,
"roc": 0.0578
}
},
"Software (System & Application)": {
"us": {
"n": 309,
"beta": 1.2766,
"de": 0.0558,
"tax": 0.0551,
"ubeta": 1.2482,
"wacc": 0.0934,
"ke": 0.0964,
"margin": 0.3298,
"netm": 0.2549,
"roe": 0.2962,
"roc": 0.2932
},
"gl": {
"n": 1532,
"beta": 1.354,
"de": 0.0584,
"tax": 0.0904,
"ubeta": 1.331,
"wacc": 0.1118,
"ke": 0.1157,
"margin": 0.2741,
"netm": 0.2083,
"roe": 0.2367,
"roc": 0.2372
}
},
"Steel": {
"us": {
"n": 19,
"beta": 1.0628,
"de": 0.2351,
"tax": 0.0928,
"ubeta": 0.9449,
"wacc": 0.0776,
"ke": 0.0869,
"margin": 0.041,
"netm": 0.0193,
"roe": 0.0368,
"roc": 0.0672
},
"gl": {
"n": 719,
"beta": 1.1289,
"de": 0.4734,
"tax": 0.1455,
"ubeta": 0.9293,
"wacc": 0.0838,
"ke": 0.1031,
"margin": 0.0485,
"netm": 0.0242,
"roe": 0.0395,
"roc": 0.0509
}
},
"Telecom (Wireless)": {
"us": {
"n": 12,
"beta": 0.5381,
"de": 0.5195,
"tax": 0.0402,
"ubeta": 0.3924,
"wacc": 0.0548,
"ke": 0.0635,
"margin": 0.2098,
"netm": 0.1224,
"roe": 0.1606,
"roc": 0.1037
},
"gl": {
"n": 101,
"beta": 0.7824,
"de": 0.4997,
"tax": 0.1767,
"ubeta": 0.6028,
"wacc": 0.0693,
"ke": 0.0836,
"margin": 0.1583,
"netm": 0.1114,
"roe": 0.1345,
"roc": 0.0929
}
},
"Telecom. Equipment": {
"us": {
"n": 57,
"beta": 0.9232,
"de": 0.0922,
"tax": 0.0706,
"ubeta": 0.8873,
"wacc": 0.0772,
"ke": 0.0807,
"margin": 0.207,
"netm": 0.1609,
"roe": 0.2496,
"roc": 0.2547
},
"gl": {
"n": 437,
"beta": 1.3279,
"de": 0.0962,
"tax": 0.0827,
"ubeta": 1.2979,
"wacc": 0.1082,
"ke": 0.1143,
"margin": 0.1103,
"netm": 0.0849,
"roe": 0.1406,
"roc": 0.1273
}
},
"Telecom. Services": {
"us": {
"n": 39,
"beta": 0.6287,
"de": 0.9606,
"tax": 0.034,
"ubeta": 0.3815,
"wacc": 0.0539,
"ke": 0.0675,
"margin": 0.2047,
"netm": 0.142,
"roe": 0.1982,
"roc": 0.1204
},
"gl": {
"n": 283,
"beta": 0.729,
"de": 0.7318,
"tax": 0.154,
"ubeta": 0.4963,
"wacc": 0.0648,
"ke": 0.0805,
"margin": 0.1609,
"netm": 0.0943,
"roe": 0.1279,
"roc": 0.0987
}
},
"Tobacco": {
"us": {
"n": 10,
"beta": 0.7943,
"de": 0.2297,
"tax": 0.1477,
"ubeta": 0.6903,
"wacc": 0.0694,
"ke": 0.0749,
"margin": 0.4354,
"netm": 0.2665,
"roe": None,
"roc": 0.6308
},
"gl": {
"n": 48,
"beta": 0.4273,
"de": 0.2366,
"tax": 0.2013,
"ubeta": 0.3743,
"wacc": 0.0597,
"ke": 0.0636,
"margin": 0.3267,
"netm": 0.1922,
"roe": 0.2864,
"roc": 0.2417
}
},
"Transportation": {
"us": {
"n": 19,
"beta": 0.8599,
"de": 0.3645,
"tax": 0.0854,
"ubeta": 0.7115,
"wacc": 0.0672,
"ke": 0.0779,
"margin": 0.0757,
"netm": 0.0823,
"roe": 0.3658,
"roc": 0.13
},
"gl": {
"n": 451,
"beta": 0.9639,
"de": 0.5347,
"tax": 0.1759,
"ubeta": 0.7475,
"wacc": 0.0761,
"ke": 0.0938,
"margin": 0.0721,
"netm": 0.0512,
"roe": 0.1403,
"roc": 0.0866
}
},
"Transportation (Railroads)": {
"us": {
"n": 4,
"beta": 0.9751,
"de": 0.2779,
"tax": 0.1698,
"ubeta": 0.8137,
"wacc": 0.0727,
"ke": 0.083,
"margin": 0.3741,
"netm": 0.2473,
"roe": 0.2907,
"roc": 0.1424
},
"gl": {
"n": 54,
"beta": 0.72,
"de": 0.4744,
"tax": 0.2419,
"ubeta": 0.5544,
"wacc": 0.0674,
"ke": 0.08,
"margin": 0.2345,
"netm": 0.1567,
"roe": 0.1231,
"roc": 0.0779
}
},
"Trucking": {
"us": {
"n": 26,
"beta": 1.0113,
"de": 0.2523,
"tax": 0.126,
"ubeta": 0.8689,
"wacc": 0.0752,
"ke": 0.0846,
"margin": 0.0689,
"netm": 0.0379,
"roe": 0.076,
"roc": 0.093
},
"gl": {
"n": 130,
"beta": 0.8498,
"de": 0.3987,
"tax": 0.2003,
"ubeta": 0.6772,
"wacc": 0.0748,
"ke": 0.0873,
"margin": 0.0745,
"netm": 0.0335,
"roe": 0.072,
"roc": 0.0844
}
},
"Utility (General)": {
"us": {
"n": 14,
"beta": 0.2394,
"de": 0.8148,
"tax": 0.1277,
"ubeta": 0.1491,
"wacc": 0.0436,
"ke": 0.0502,
"margin": 0.2349,
"netm": 0.1418,
"roe": 0.1042,
"roc": 0.0599
},
"gl": {
"n": 52,
"beta": 0.5039,
"de": 0.7623,
"tax": 0.1854,
"ubeta": 0.3344,
"wacc": 0.0561,
"ke": 0.0679,
"margin": 0.1522,
"netm": 0.0779,
"roe": 0.1055,
"roc": 0.0799
}
},
"Utility (Water)": {
"us": {
"n": 14,
"beta": 0.4127,
"de": 0.6236,
"tax": 0.1119,
"ubeta": 0.2825,
"wacc": 0.0493,
"ke": 0.0579,
"margin": 0.3372,
"netm": 0.2116,
"roe": 0.1028,
"roc": 0.0896
},
"gl": {
"n": 106,
"beta": 0.7046,
"de": 0.9127,
"tax": 0.1609,
"ubeta": 0.4453,
"wacc": 0.062,
"ke": 0.0792,
"margin": 0.266,
"netm": 0.1484,
"roe": 0.0981,
"roc": 0.0674
}
}
}


# ----------------------------------------------------------------------------
# Mapeo industria Yahoo -> industria Damodaran (el primero que coincida gana)
# ----------------------------------------------------------------------------
_MAP = [
    ("reit - retail", "Retail (REITs)"), ("reit - mortgage", "Financial Svcs. (Non-bank & Insurance)"),
    ("reit", "R.E.I.T."), ("real estate - development", "Real Estate (Development)"),
    ("real estate services", "Real Estate (Operations & Services)"), ("real estate - diversified", "Real Estate (General/Diversified)"),
    ("banks - diversified", "Bank (Money Center)"), ("banks - regional", "Banks (Regional)"), ("banks", "Banks (Regional)"),
    ("insurance - life", "Insurance (Life)"), ("insurance - property", "Insurance (Prop/Cas.)"),
    ("insurance - specialty", "Insurance (Prop/Cas.)"), ("insurance - reinsurance", "Reinsurance"),
    ("insurance brokers", "Insurance (General)"), ("insurance", "Insurance (General)"),
    ("asset management", "Investments & Asset Management"), ("capital markets", "Brokerage & Investment Banking"),
    ("mortgage finance", "Financial Svcs. (Non-bank & Insurance)"), ("credit services", "Financial Svcs. (Non-bank & Insurance)"),
    ("financial data", "Financial Svcs. (Non-bank & Insurance)"), ("financial conglomerates", "Financial Svcs. (Non-bank & Insurance)"),
    ("software", "Software (System & Application)"), ("information technology services", "Computer Services"),
    ("semiconductor equipment", "Semiconductor Equip"), ("semiconductor", "Semiconductor"),
    ("consumer electronics", "Electronics (Consumer & Office)"), ("computer hardware", "Computers/Peripherals"),
    ("communication equipment", "Telecom. Equipment"), ("electronic components", "Electronics (General)"),
    ("scientific & technical", "Electronics (General)"), ("solar", "Green & Renewable Energy"),
    ("electronics & computer distribution", "Retail (Distributors)"),
    ("internet content", "Software (Internet)"), ("telecom", "Telecom. Services"), ("entertainment", "Entertainment"),
    ("broadcasting", "Broadcasting"), ("advertising", "Advertising"), ("publishing", "Publishing & Newspapers"),
    ("electronic gaming", "Software (Entertainment)"),
    ("internet retail", "Retail (General)"), ("auto manufacturers", "Auto & Truck"), ("auto parts", "Auto Parts"),
    ("auto & truck dealerships", "Retail (Automotive)"), ("restaurants", "Restaurant/Dining"),
    ("home improvement", "Retail (Building Supply)"), ("department stores", "Retail (General)"),
    ("discount stores", "Retail (General)"), ("specialty retail", "Retail (Special Lines)"),
    ("apparel retail", "Retail (Special Lines)"), ("apparel manufacturing", "Apparel"), ("luxury goods", "Apparel"),
    ("textile", "Apparel"), ("footwear", "Shoe"), ("lodging", "Hotel/Gaming"), ("resorts", "Hotel/Gaming"),
    ("gambling", "Hotel/Gaming"), ("casino", "Hotel/Gaming"), ("leisure", "Recreation"), ("recreational", "Recreation"),
    ("travel services", "Recreation"), ("residential construction", "Homebuilding"), ("furnishings", "Furn/Home Furnishings"),
    ("packaging", "Packaging & Container"), ("education", "Education"), ("personal services", "Business & Consumer Services"),
    ("beverages - non-alcoholic", "Beverage (Soft)"), ("beverages", "Beverage (Alcoholic)"),
    ("packaged foods", "Food Processing"), ("confectioners", "Food Processing"), ("farm products", "Farming/Agriculture"),
    ("food distribution", "Food Wholesalers"), ("grocery", "Retail (Grocery and Food)"),
    ("household & personal", "Household Products"), ("tobacco", "Tobacco"),
    ("drug manufacturers", "Drugs (Pharmaceutical)"), ("biotechnology", "Drugs (Biotechnology)"),
    ("pharmaceutical retailers", "Retail (Grocery and Food)"), ("medical devices", "Healthcare Products"),
    ("medical instruments", "Healthcare Products"), ("diagnostics", "Healthcare Products"),
    ("healthcare plans", "Hospitals/Healthcare Facilities"), ("medical care", "Hospitals/Healthcare Facilities"),
    ("medical distribution", "Healthcare Support Services"), ("health information", "Heathcare Information and Technology"),
    ("aerospace", "Aerospace/Defense"), ("airlines", "Air Transport"), ("airports", "Transportation"),
    ("railroads", "Transportation (Railroads)"), ("trucking", "Trucking"), ("integrated freight", "Transportation"),
    ("marine shipping", "Shipbuilding & Marine"), ("machinery", "Machinery"), ("tools & accessories", "Machinery"),
    ("electrical equipment", "Electrical Equipment"), ("engineering & construction", "Engineering/Construction"),
    ("infrastructure operations", "Engineering/Construction"), ("building products", "Building Materials"),
    ("waste management", "Environmental & Waste Services"), ("pollution", "Environmental & Waste Services"),
    ("specialty business services", "Business & Consumer Services"), ("staffing", "Business & Consumer Services"),
    ("consulting", "Business & Consumer Services"), ("security & protection", "Business & Consumer Services"),
    ("rental & leasing", "Business & Consumer Services"), ("conglomerates", "Diversified"),
    ("industrial distribution", "Retail (Distributors)"),
    ("oil & gas integrated", "Oil/Gas (Integrated)"), ("oil & gas e&p", "Oil/Gas (Production and Exploration)"),
    ("oil & gas midstream", "Oil/Gas Distribution"), ("oil & gas equipment", "Oilfield Svcs/Equip."),
    ("oil & gas drilling", "Oilfield Svcs/Equip."), ("oil & gas refining", "Oil/Gas (Integrated)"),
    ("thermal coal", "Coal & Related Energy"), ("coal", "Coal & Related Energy"), ("uranium", "Coal & Related Energy"),
    ("specialty chemicals", "Chemical (Specialty)"), ("chemicals", "Chemical (Basic)"),
    ("agricultural inputs", "Chemical (Basic)"), ("steel", "Steel"), ("gold", "Precious Metals"),
    ("silver", "Precious Metals"), ("copper", "Metals & Mining"), ("aluminum", "Metals & Mining"),
    ("industrial metals", "Metals & Mining"), ("other precious", "Precious Metals"),
    ("building materials", "Construction Supplies"), ("lumber", "Paper/Forest Products"), ("paper", "Paper/Forest Products"),
    ("utilities - regulated water", "Utility (Water)"), ("utilities - regulated", "Utility (General)"),
    ("utilities - diversified", "Utility (General)"), ("utilities - independent", "Power"),
    ("utilities - renewable", "Green & Renewable Energy"),
]


def map_industry(yahoo_industry: str):
    import re
    s = re.sub(r"\s*[—–]\s*", " - ", (yahoo_industry or "").strip().lower())   # raya larga -> " - "
    if not s:
        return None
    for key, name in _MAP:
        if key in s:
            return name if name in IND else None
    return None


def industry_names():
    return sorted(IND)


MIN_MUESTRA_US = 20   # empresas mínimas en la muestra de EE.UU. para usarla; si hay menos, se usa la global


def get_ref(name, country=""):
    """Devuelve (dict, 'US'|'Global') para la industria; US si la empresa es de EE.UU. o no se sabe el país."""
    if not name or name not in IND:
        return None, ""
    us = (country or "").strip().lower() in ("", "united states", "usa", "us")
    order = ("us", "gl") if us else ("gl", "us")
    chica = False
    if us:
        u, g = IND[name].get("us") or {}, IND[name].get("gl") or {}
        # Regla A (decidida el 17/10/2026): con menos de MIN_MUESTRA_US empresas en EE.UU., el promedio es ruidoso:
        # se usa la muestra global (si tiene más empresas y trae beta).
        if (u.get("n") or 0) < MIN_MUESTRA_US and g.get("beta") is not None and (g.get("n") or 0) > (u.get("n") or 0):
            order, chica = ("gl", "us"), True
    for r in order:
        if IND[name].get(r) and IND[name][r].get("beta") is not None:
            return IND[name][r], ("EE.UU." if r == "us" else ("Global, por muestra chica en EE.UU." if chica else "Global"))
    return None, ""


USE_DAMODARAN_LIST = True   # v2.43: buscar primero en la planilla de Damodaran (los tests y comparaciones la pueden apagar)


def attach(co, model, manual_name=None):
    """Devuelve (co con datos de industria, nombre de industria o None, cómo se obtuvo)."""
    from dataclasses import replace
    name, how = None, ""
    if manual_name and manual_name in IND:
        name, how = manual_name, "elegida por vos"
    else:
        # v2.43: primero la planilla de Damodaran (su industria exacta para esa empresa); si no está, la regla de Yahoo.
        if USE_DAMODARAN_LIST:
            from damodaran_map import lookup
            hit = lookup(getattr(co, "ticker", ""), getattr(co, "name", ""), getattr(co, "country", ""))
            if hit and hit[0] in IND and get_ref(hit[0], getattr(co, "country", ""))[0]:
                name, how = hit[0], f"según la planilla de Damodaran ({hit[1]})"
        if not name:
            name = map_industry(getattr(co, "industry", ""))
            if name:
                how = f"detectada desde Yahoo ({co.industry}): no figura en la planilla de Damodaran"
    ref, region = get_ref(name, getattr(co, "country", ""))
    if not ref:
        return co, None, ""
    fin = model == "ER"
    return replace(co, ind_name=name, ind_region=region,
                   ind_ubeta=None if fin else ref.get("ubeta"),
                   ind_beta_lev=ref.get("beta") if fin else None,
                   ind_roc=None if fin else ref.get("roc"),
                   ind_margin=None if fin else ref.get("margin"),
                   ind_de=None if fin else ref.get("de")), name, how
