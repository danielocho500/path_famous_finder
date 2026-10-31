"""Enrich all existing Facts, Sources, and Events in Neo4j with geographic locations.

Supports --dry-run (default) and --apply.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver

# 1. Geographic mappings for all 82 Facts by ID
FACT_LOCATIONS = {
    # Arts performances
    "b6fad8f5-1ef2-4059-9cae-15cb4a59e509": {
        "name": "Pepsi Center WTC, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.3956,
        "lng": -99.1746,
    },
    "5fb8ebc2-4c4a-4f92-bdb0-27482b693c5a": {
        "name": "Pepsi Center WTC, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.3956,
        "lng": -99.1746,
    },
    "0b4c8c27-c44d-4061-bfe2-c07ac9d68ca8": {
        "name": "Auditorio Nacional, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.4246,
        "lng": -99.1919,
    },
    "d8aacf8a-626f-4129-826a-7c19667f6c99": {
        "name": "Auditorio Nacional, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.4246,
        "lng": -99.1919,
    },
    "2b86ed35-ec3c-461b-b6b5-093b7e077654": {
        "name": "Estadio Santiago Bernabéu, Madrid",
        "city": "Madrid",
        "country": "ES",
        "lat": 40.4530,
        "lng": -3.6883,
    },
    "1708f701-d2bc-41ca-b8d8-c0478262a47b": {
        "name": "Estadio Santiago Bernabéu, Madrid",
        "city": "Madrid",
        "country": "ES",
        "lat": 40.4530,
        "lng": -3.6883,
    },
    # British Royal Family & 20th Century
    "935dc8a0-1701-4128-84c5-67e5aa113d41": {
        "name": "Royal Opera House, Covent Garden, Londres",
        "city": "Londres",
        "country": "GB",
        "lat": 51.5129,
        "lng": -0.1222,
    },
    "1f95a209-0e53-4bb0-8b4a-e4294fab8d20": {
        "name": "Bruton Street, Mayfair, Londres",
        "city": "Londres",
        "country": "GB",
        "lat": 51.5103,
        "lng": -0.1444,
    },
    "875d01d2-6da8-4f3e-b4f6-12aaf8dd9954": {
        "name": "York Cottage, Sandringham",
        "city": "Sandringham",
        "country": "GB",
        "lat": 52.8282,
        "lng": 0.5139,
    },
    "e4ccaae7-c738-490a-9d0c-5fba959f3cc7": {
        "name": "Palacio de Buckingham, Londres",
        "city": "Londres",
        "country": "GB",
        "lat": 51.5014,
        "lng": -0.1419,
    },
    "a7f705ad-3246-40c7-a584-23c4d5e7986a": {
        "name": "Ashram de Santiniketan, Bolpur",
        "city": "Santiniketan",
        "country": "IN",
        "lat": 23.6788,
        "lng": 87.6775,
    },
    "301b6375-6f43-4c65-8ffd-a33e7fa6ac50": {
        "name": "Residencia de Einstein en Caputh",
        "city": "Caputh / Berlín",
        "country": "DE",
        "lat": 52.3486,
        "lng": 13.0163,
    },
    "5fb21b32-f5c6-42f3-878a-b8f2edf7bed7": {
        "name": "Universidad de Berlín (Humboldt-Universität), Berlín",
        "city": "Berlín",
        "country": "DE",
        "lat": 52.5180,
        "lng": 13.3933,
    },
    "2f6e63cf-d496-45e8-a2f1-768dadfd1049": {
        "name": "Universidad de Berlín (Humboldt-Universität), Berlín",
        "city": "Berlín",
        "country": "DE",
        "lat": 52.5180,
        "lng": 13.3933,
    },
    "a1edc469-360f-467f-b791-275e3c1e62a4": {
        "name": "Real Academia Prusiana de Ciencias, Berlín",
        "city": "Berlín",
        "country": "DE",
        "lat": 52.5163,
        "lng": 13.3908,
    },
    # Enlightenment & 18th Century
    "ac3a3f4a-6e69-4968-a0b3-c752770bc6de": {
        "name": "Casa Blanca, Washington D.C.",
        "city": "Washington D.C.",
        "country": "US",
        "lat": 38.8977,
        "lng": -77.0365,
    },
    "d78f61b1-dd20-4b2f-b62c-8b94dd6e790a": {
        "name": "Palacio de Versalles",
        "city": "Versalles",
        "country": "FR",
        "lat": 48.8049,
        "lng": 2.1204,
    },
    "3e97aaa1-bf3f-4a4c-a94a-9411cd2c4bbf": {
        "name": "Palacio de Versalles",
        "city": "Versalles",
        "country": "FR",
        "lat": 48.8049,
        "lng": 2.1204,
    },
    "227ea3c1-681b-4d19-a187-0b474cb9e135": {
        "name": "Academia de Ciencias de París, Collège des Quatre-Nations",
        "city": "París",
        "country": "FR",
        "lat": 48.8570,
        "lng": 2.3370,
    },
    "e0551359-e566-4810-8cdf-569f350f9a86": {
        "name": "Salón de Ninon de Lenclos, Rue des Tournelles, París",
        "city": "París",
        "country": "FR",
        "lat": 48.8558,
        "lng": 2.3683,
    },
    "91b5a212-4a66-4bc2-ad22-763e4018e197": {
        "name": "Picpus, París",
        "city": "París",
        "country": "FR",
        "lat": 48.8436,
        "lng": 2.3992,
    },
    # 17th Century (Descartes, Mersenne, Galileo)
    "76822960-b2e4-4f59-b53f-2cfddb962d75": {
        "name": "Palacio Real de Tre Kronor, Estocolmo",
        "city": "Estocolmo",
        "country": "SE",
        "lat": 59.3268,
        "lng": 18.0717,
    },
    "695f028b-40c1-485e-a41c-b2b8a1d49887": {
        "name": "Convento de los Mínimos de París",
        "city": "París",
        "country": "FR",
        "lat": 48.8553,
        "lng": 2.3667,
    },
    "32953805-6d9a-433e-ab4e-9fec1cf2e5ac": {
        "name": "París y Villa Il Gioiello, Arcetri (Florencia)",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7483,
        "lng": 11.2558,
    },
    # Renaissance (Medici, Sforza, Machiavelli, Da Vinci, Michelangelo, Raphael)
    "9d16341c-5eb6-44fc-af52-9f177ab0ff52": {
        "name": "Palazzo Pitti y Corte Medicea, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7653,
        "lng": 11.2500,
    },
    "beca872f-0e09-432f-a692-0a6ed4a08cc3": {
        "name": "Palazzo Pitti, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7653,
        "lng": 11.2500,
    },
    "6c09eb47-3d03-41d9-bf38-f3c5761271b1": {
        "name": "Palazzo Vecchio, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7694,
        "lng": 11.2562,
    },
    "85a66bae-352c-44e1-8250-7b61aadc4ab1": {
        "name": "Forlì y Florencia",
        "city": "Forlì",
        "country": "IT",
        "lat": 44.2227,
        "lng": 12.0407,
    },
    "00ddf5b4-1cae-493e-957b-918c029af0f2": {
        "name": "Rocca di Ravaldino, Forlì",
        "city": "Forlì",
        "country": "IT",
        "lat": 44.2144,
        "lng": 12.0353,
    },
    "dadede0d-896a-4096-88e6-0fc171c005e3": {
        "name": "Rocca di Ravaldino, Forlì",
        "city": "Forlì",
        "country": "IT",
        "lat": 44.2144,
        "lng": 12.0353,
    },
    "d45e3501-228b-4a9b-a667-1984b157d9d7": {
        "name": "Rocca Sforzesca di Imola",
        "city": "Imola",
        "country": "IT",
        "lat": 44.3533,
        "lng": 11.7141,
    },
    "51c6e30a-943a-4ad1-951c-cc786a572d1a": {
        "name": "Imola y Palazzo Vecchio de Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7694,
        "lng": 11.2562,
    },
    "9fc089d0-befb-43c7-882e-0b8d7734c216": {
        "name": "Rocca di Ravaldino, Forlì",
        "city": "Forlì",
        "country": "IT",
        "lat": 44.2144,
        "lng": 12.0353,
    },
    "8708a5f9-1c42-4ad2-a1fb-d3ccacb6a973": {
        "name": "Castello Sforzesco, Milán",
        "city": "Milán",
        "country": "IT",
        "lat": 45.4705,
        "lng": 9.1793,
    },
    "c5a444ba-bc14-4a0f-84fc-fb9c2277f6fa": {
        "name": "Piazza della Signoria, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7696,
        "lng": 11.2558,
    },
    "8a0616c2-cd8c-4f1c-9647-cbf7cf01af16": {
        "name": "Palazzo Vecchio, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7694,
        "lng": 11.2562,
    },
    "69cd38d5-42b3-4650-be1c-280fe70da80b": {
        "name": "Bottega di Verrocchio, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7711,
        "lng": 11.2580,
    },
    "abd8b86a-d3e7-4388-bf0c-80b05332f812": {
        "name": "Corte Ducal Sforzesca, Milán",
        "city": "Milán",
        "country": "IT",
        "lat": 45.4705,
        "lng": 9.1793,
    },
    "dd6e2643-0481-4f42-b645-ac4575dbc76c": {
        "name": "Corte Sforzesca de Milán",
        "city": "Milán",
        "country": "IT",
        "lat": 45.4705,
        "lng": 9.1793,
    },
    "14f829ea-117e-4faf-aa58-538a558836ce": {
        "name": "Castello di Pavia",
        "city": "Pavía",
        "country": "IT",
        "lat": 45.1917,
        "lng": 9.1583,
    },
    "5c83885c-b1e9-41da-9b0c-d5a1f63bc36f": {
        "name": "Manoir du Clos Lucé, Amboise",
        "city": "Amboise",
        "country": "FR",
        "lat": 47.4103,
        "lng": 0.9917,
    },
    "b4716d73-98ee-4ac9-ae18-6c3d3b832e63": {
        "name": "Palacio Apostólico Vaticano, Roma",
        "city": "Roma",
        "country": "VA",
        "lat": 41.9038,
        "lng": 12.4547,
    },
    "9dcf56cc-5803-43ef-83ac-d1348b329214": {
        "name": "Jardín de San Marcos, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7786,
        "lng": 11.2592,
    },
    "c5068c1f-ae95-4409-a312-406089f4f62f": {
        "name": "Villa Medicea de Castello, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.8189,
        "lng": 11.2289,
    },
    "83b84c1f-29fb-48e0-96fb-ed9ccb76797f": {
        "name": "Capilla Sixtina, Palacio Apostólico Vaticano",
        "city": "Roma",
        "country": "VA",
        "lat": 41.9029,
        "lng": 12.4545,
    },
    "e9153d51-2fda-48b6-a97d-146a63295472": {
        "name": "Estancias de Rafael, Palacio Apostólico Vaticano",
        "city": "Roma",
        "country": "VA",
        "lat": 41.9038,
        "lng": 12.4547,
    },
    "cc0e5418-0c98-4730-ac94-3ba1e496c6be": {
        "name": "Palazzo Medici Riccardi, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7753,
        "lng": 11.2556,
    },
    "047e90a2-34d2-410a-bc34-3fd8aca2c218": {
        "name": "Palazzo Medici, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7753,
        "lng": 11.2556,
    },
    "5777221d-6e61-47d0-b43d-decd62d8e0c9": {
        "name": "Palazzo Medici y Santa Maria Novella, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7746,
        "lng": 11.2494,
    },
    "55ff23be-4e0f-4544-b38c-fd01cb0334bf": {
        "name": "Catedral de Santa Maria del Fiore, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7731,
        "lng": 11.2560,
    },
    "2534182b-0d6f-49c3-baca-dd47053ca163": {
        "name": "Convento de Santa Maria Novella, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7746,
        "lng": 11.2494,
    },
    "6795be95-849c-4a7f-a63e-323589dda822": {
        "name": "Academia Neoplatónica, Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7753,
        "lng": 11.2556,
    },
    "981dc5f0-3587-435b-8270-d38170787b38": {
        "name": "Ferrara y Florencia",
        "city": "Florencia",
        "country": "IT",
        "lat": 43.7746,
        "lng": 11.2494,
    },
    # Byzantine & Medieval (Palaiologos, Komnenos, Macedonian)
    "96369aa2-2808-44ee-9e59-7bb30175d07c": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "57c0837f-d645-4165-8c72-740e731c5d8e": {
        "name": "Basílica de Santa Sofía, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0086,
        "lng": 28.9802,
    },
    "b832cde1-d9d4-406e-9c5a-acc47f4ebf32": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "5e903d4d-6d83-4a7a-9b0f-c0c47b7b18ae": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "93c44b04-5244-4b19-9f63-23807a1788c5": {
        "name": "Palacio de Blanquerna, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0378,
        "lng": 28.9408,
    },
    "02f94be2-2d22-46f9-a004-637baf6fd3ae": {
        "name": "Palacio del Louvre y Saint-Denis, París",
        "city": "París",
        "country": "FR",
        "lat": 48.8606,
        "lng": 2.3376,
    },
    "17de7f3a-86b9-4643-a07f-b8ee34fea598": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "8f284fc5-d0e2-4840-b893-04aed5e98caf": {
        "name": "Catedral Imperial de Santa Sofía, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0086,
        "lng": 28.9802,
    },
    "97f6fddf-8448-4c91-be9f-d330a8240804": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "ec45360b-b30d-41d8-a44c-446209d941c0": {
        "name": "Basílica de Santa Sofía, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0086,
        "lng": 28.9802,
    },
    "b4e80871-3d8e-4abd-9f2d-2a0b52d5848d": {
        "name": "Nicea y Constantinopla",
        "city": "Nicea (Iznik)",
        "country": "TR",
        "lat": 40.4286,
        "lng": 29.7214,
    },
    "bddfd473-7792-4fa2-a00c-31c89b54824a": {
        "name": "Monasterio de Cora y Palacio de Blanquerna",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0311,
        "lng": 28.9392,
    },
    "6b25b01c-8f3e-4377-b4ef-1edbebad2625": {
        "name": "Tracia y Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0086,
        "lng": 28.9802,
    },
    "527b39d2-7329-433d-a2aa-802521ce46fd": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "d8679b84-8fae-4c90-8df0-4def012f384c": {
        "name": "Corte Imperial de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "be30de5e-079b-4d98-9657-fbb2feecbafa": {
        "name": "Cámara Púrpura, Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "8487f4a7-c1ac-46c5-9ebd-ac12fc63fa4f": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "f6a4a4f2-9e22-4982-835a-7bb287801903": {
        "name": "Palacio de Blanquerna, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0378,
        "lng": 28.9408,
    },
    "2736703e-dda2-4979-b6c6-526b2de81fe7": {
        "name": "Palacio de Blanquerna, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0378,
        "lng": 28.9408,
    },
    "220be5de-a02f-44cc-ac09-9db23a1864cd": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "c9184db5-fe48-4741-a373-13aef40fcc47": {
        "name": "Nicomedia (Izmit)",
        "city": "Nicomedia (Izmit)",
        "country": "TR",
        "lat": 40.7654,
        "lng": 29.9408,
    },
    "4c612e43-206b-47f7-b86b-992396e5fa6d": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "5caae94b-d964-4c2c-bd3b-abb9a2a85295": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "ce6a7e8b-140d-4a7c-aee0-bbc5e1fad274": {
        "name": "Quersoneso, Crimea",
        "city": "Quersoneso (Sebastopol)",
        "country": "UA",
        "lat": 44.6111,
        "lng": 33.4933,
    },
    "0c6a50c1-3f1a-48c2-89a0-ed069ba4bce6": {
        "name": "Cámara Púrpura, Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "eff7a52e-fe92-4f29-9bcc-e90de39cffb3": {
        "name": "Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "1a78b185-d1a9-46f5-bcbf-3985bee410f7": {
        "name": "Cámara Púrpura, Gran Palacio de Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "9af7a64c-1f2d-4592-8f8a-ee10f30f33b1": {
        "name": "Patriarcado de Constantinopla y Gran Palacio",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0054,
        "lng": 28.9768,
    },
    "170f3c3c-8bcd-4c0e-8783-6fc66a6969f1": {
        "name": "Basílica de Santa Sofía, Constantinopla",
        "city": "Constantinopla (Estambul)",
        "country": "TR",
        "lat": 41.0086,
        "lng": 28.9802,
    },
}

# 2. Geographic mappings for Events
EVENT_LOCATIONS = {
    "209c6c4f-aeb4-47ef-9db0-055319c715a5": {
        "name": "Pepsi Center WTC, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.3956,
        "lng": -99.1746,
    },
    "e752d960-209a-4817-84e9-9a474ef9dec6": {
        "name": "Auditorio Nacional, Ciudad de México",
        "city": "Ciudad de México",
        "country": "MX",
        "lat": 19.4246,
        "lng": -99.1919,
    },
    "a0de0880-ee0c-4846-a177-4aa462437b93": {
        "name": "Estadio Santiago Bernabéu, Madrid, España",
        "city": "Madrid",
        "country": "ES",
        "lat": 40.4530,
        "lng": -3.6883,
    },
}


def location_for_source(source_data):
    """Derive repository / publisher geographic location for a source."""
    pub = (source_data.get("publisher") or "").lower()
    auth = (source_data.get("author") or "").lower()
    title = (source_data.get("title") or "").lower()
    url = (source_data.get("url") or "").lower()

    if "firenze" in pub or "florencia" in pub or "medici archive" in pub or "medici" in auth:
        return {"name": "Archivio di Stato di Firenze", "city": "Florencia", "country": "IT", "lat": 43.7696, "lng": 11.2657}
    if "milano" in pub or "archivio di stato di milano" in pub:
        return {"name": "Archivio di Stato di Milano", "city": "Milán", "country": "IT", "lat": 45.4697, "lng": 9.2001}
    if "bibliothèque nationale" in pub or "bnf" in pub or "saint-denys" in title:
        return {"name": "Bibliothèque Nationale de France (BnF)", "city": "París", "country": "FR", "lat": 48.8336, "lng": 2.3758}
    if "belles lettres" in pub or "institut français d'études byzantines" in pub:
        return {"name": "Institut Français d'Études Byzantines / Les Belles Lettres", "city": "París", "country": "FR", "lat": 48.8519, "lng": 2.3364}
    if "vatican" in pub or "segreto vaticano" in pub:
        return {"name": "Archivio Apostolico Vaticano", "city": "Ciudad del Vaticano", "country": "VA", "lat": 41.9048, "lng": 12.4545}
    if "cambridge university press" in pub:
        return {"name": "Cambridge University Press", "city": "Cambridge", "country": "GB", "lat": 52.1939, "lng": 0.1287}
    if "oxford university press" in pub or "warburg" in pub:
        return {"name": "Oxford University Press", "city": "Oxford", "country": "GB", "lat": 51.7587, "lng": -1.2682}
    if "royal household" in pub or "royal archives" in auth or "national archives" in pub and "british" in pub:
        return {"name": "The National Archives (Kew) / Royal Household", "city": "Londres", "country": "GB", "lat": 51.4816, "lng": -0.2798}
    if "royal opera house" in pub:
        return {"name": "Royal Opera House Covent Garden", "city": "Londres", "country": "GB", "lat": 51.5129, "lng": -0.1222}
    if "penguin" in pub:
        return {"name": "Penguin Classics", "city": "Londres", "country": "GB", "lat": 51.5033, "lng": -0.1195}
    if "de gruyter" in pub or "weber" in pub or "bonn" in pub or "corpus scriptorum historiae byzantinae" in pub:
        return {"name": "De Gruyter / Corpus Scriptorum Historiae Byzantinae", "city": "Berlín", "country": "DE", "lat": 52.5058, "lng": 13.3547}
    if "prussian academy" in pub or "einstein archives" in pub:
        return {"name": "Preußische Akademie der Wissenschaften / Einstein Archives", "city": "Berlín", "country": "DE", "lat": 52.5163, "lng": 13.3908}
    if "university of berlin" in pub:
        return {"name": "Universitätsarchiv der Humboldt-Universität zu Berlin", "city": "Berlín", "country": "DE", "lat": 52.5180, "lng": 13.3933}
    if "library of congress" in pub or "u.s. department of state" in pub or "national archives" in pub:
        return {"name": "Library of Congress / National Archives", "city": "Washington D.C.", "country": "US", "lat": 38.8887, "lng": -77.0047}
    if "dumbarton oaks" in pub or "harvard" in pub:
        return {"name": "Dumbarton Oaks Research Library", "city": "Washington D.C.", "country": "US", "lat": 38.9139, "lng": -77.0628}
    if "yale university press" in pub:
        return {"name": "Yale University Press", "city": "New Haven", "country": "US", "lat": 41.3111, "lng": -72.9267}
    if "mediaeval academy of america" in pub:
        return {"name": "Mediaeval Academy of America", "city": "Cambridge (MA)", "country": "US", "lat": 42.3736, "lng": -71.1097}
    if "rutgers university press" in pub:
        return {"name": "Rutgers University Press", "city": "New Brunswick", "country": "US", "lat": 40.4983, "lng": -74.4448}
    if "university of massachusetts" in pub:
        return {"name": "University of Massachusetts Press", "city": "Amherst", "country": "US", "lat": 42.3868, "lng": -72.5301}
    if "visva-bharati" in pub or "national book trust" in pub:
        return {"name": "Visva-Bharati Central Archives", "city": "Santiniketan", "country": "IN", "lat": 23.6788, "lng": 87.6775}
    if "swedish" in pub or "vitterhetsakademien" in pub:
        return {"name": "Riksarkivet (National Archives of Sweden)", "city": "Estocolmo", "country": "SE", "lat": 59.3275, "lng": 18.0267}
    if "el país" in pub or "elpais.com" in url:
        return {"name": "Ediciones El País", "city": "Madrid", "country": "ES", "lat": 40.4357, "lng": -3.6186}
    if "el universal" in pub or "ocesa" in pub or "cineframe" in pub or "indie rocks" in pub:
        return {"name": "Sede Editorial / Producción CDMX", "city": "Ciudad de México", "country": "MX", "lat": 19.4326, "lng": -99.1332}
    if "brill" in pub:
        return {"name": "Brill Academic Publishers", "city": "Leiden", "country": "NL", "lat": 52.1601, "lng": 4.4970}
    if "centre for byzantine studies" in pub or "varzos" in auth:
        return {"name": "Centre for Byzantine Research", "city": "Tesalónica", "country": "GR", "lat": 40.6300, "lng": 22.9536}
    if "wikipedia" in pub or "wikipedia.org" in url:
        return {"name": "Wikimedia Foundation", "city": "San Francisco", "country": "US", "lat": 37.7891, "lng": -122.4014}
    if "salerno" in pub or "repubblica fiorentina" in pub or "einaudi" in pub or "sansoni" in pub or "olschki" in pub:
        return {"name": "Archivio Storico / Sede Editoriale Firenze", "city": "Florencia", "country": "IT", "lat": 43.7696, "lng": 11.2558}

    return {"name": "Archivo / Editorial", "city": None, "country": None, "lat": None, "lng": None}


def now():
    return datetime.now(timezone.utc).isoformat()


def migrate_locations(apply=False):
    with driver.session() as session:
        # 1. Migrate Events
        events = session.run("MATCH (e:Event) RETURN e").data()
        print(f"\n--- Checking {len(events)} Events ---")
        for row in events:
            node = dict(row["e"])
            data = json.loads(node.get("data") or "{}")
            eid = node["id"]
            rev = node.get("revision", 1)
            loc = EVENT_LOCATIONS.get(eid) or {"name": data.get("place") or "Ubicación"}
            data["location"] = loc
            if not data.get("place"):
                data["place"] = loc["name"]
            print(f"Event '{data.get('name')}' -> {loc['name']} ({loc.get('city')}, {loc.get('country')})")
            if apply:
                stamp = now()
                fields = {
                    "data": json.dumps(data, ensure_ascii=False),
                    "revision": rev + 1,
                    "updated_at": stamp,
                    "location_name": loc["name"],
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                    "city": loc.get("city"),
                    "country": loc.get("country"),
                }
                session.run("MATCH (e:Event {id:$id}) SET e += $fields", id=eid, fields=fields)
                session.run(
                    "CREATE (a:AuditEntry {id:$aid, entity_id:$id, collection:'events', "
                    "action:'migrate_location', revision:$rev, at:$at})",
                    aid=str(uuid4()), id=eid, rev=rev + 1, at=stamp,
                )

        # 2. Migrate Sources
        sources = session.run("MATCH (s:Source) RETURN s").data()
        print(f"\n--- Checking {len(sources)} Sources ---")
        sources_updated = 0
        for row in sources:
            node = dict(row["s"])
            data = json.loads(node.get("data") or "{}")
            sid = node["id"]
            rev = node.get("revision", 1)
            loc = location_for_source(data)
            data["location"] = loc
            sources_updated += 1
            if sources_updated <= 5 or sources_updated % 15 == 0:
                print(f"Source [{sources_updated}] '{data.get('title')[:45]}...' -> {loc['name']} ({loc.get('city')}, {loc.get('country')})")
            if apply:
                stamp = now()
                fields = {
                    "data": json.dumps(data, ensure_ascii=False),
                    "revision": rev + 1,
                    "updated_at": stamp,
                    "location_name": loc["name"],
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                    "city": loc.get("city"),
                    "country": loc.get("country"),
                }
                session.run("MATCH (s:Source {id:$id}) SET s += $fields", id=sid, fields=fields)
                session.run(
                    "CREATE (a:AuditEntry {id:$aid, entity_id:$id, collection:'sources', "
                    "action:'migrate_location', revision:$rev, at:$at})",
                    aid=str(uuid4()), id=sid, rev=rev + 1, at=stamp,
                )

        # 3. Migrate Facts
        facts = session.run("MATCH (f:Fact) RETURN f").data()
        print(f"\n--- Checking {len(facts)} Facts ---")
        facts_updated = 0
        for row in facts:
            node = dict(row["f"])
            data = json.loads(node.get("data") or "{}")
            fid = node["id"]
            rev = node.get("revision", 1)
            loc = FACT_LOCATIONS.get(fid)
            if not loc:
                print(f"WARNING: No explicit location for fact {fid}: {data.get('type_id')}")
                loc = {"name": data.get("source_locator") or "Lugar no especificado"}
            data["location"] = loc
            facts_updated += 1
            if facts_updated <= 5 or facts_updated % 15 == 0:
                print(f"Fact [{facts_updated}] {data.get('type_id')} -> {loc['name']} ({loc.get('city')}, {loc.get('country')})")
            if apply:
                stamp = now()
                fields = {
                    "data": json.dumps(data, ensure_ascii=False),
                    "revision": rev + 1,
                    "updated_at": stamp,
                    "location_name": loc["name"],
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                    "city": loc.get("city"),
                    "country": loc.get("country"),
                }
                session.run("MATCH (f:Fact {id:$id}) SET f += $fields", id=fid, fields=fields)
                session.run(
                    "CREATE (a:AuditEntry {id:$aid, entity_id:$id, collection:'facts', "
                    "action:'migrate_location', revision:$rev, at:$at})",
                    aid=str(uuid4()), id=fid, rev=rev + 1, at=stamp,
                )

        print("\n==========================================")
        if apply:
            print(f"APPLIED! Successfully updated {len(events)} events, {sources_updated} sources, and {facts_updated} facts with geographic locations.")
        else:
            print(f"DRY RUN COMPLETE: {len(events)} events, {sources_updated} sources, and {facts_updated} facts ready to migrate. Run with --apply to write to Neo4j.")
        print("==========================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add geographic locations to existing graph entities.")
    parser.add_argument("--apply", action="store_true", help="Apply updates to Neo4j")
    args = parser.parse_args()
    migrate_locations(apply=args.apply)
