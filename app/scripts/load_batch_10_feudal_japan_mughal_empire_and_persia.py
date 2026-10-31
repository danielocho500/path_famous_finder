"""
Lote 10: Japón Feudal, el Imperio Mogol, Persia y las Grandes Dinastías de Asia (~973 – 1849 d.C.).

Figuras históricas incluidas:
1. Oda Nobunaga (Q171411) - Primer gran unificador de Japón, período Sengoku.
2. Toyotomi Hideyoshi (Q187550) - Segundo unificador de Japón, regente imperial.
3. Tokugawa Ieyasu (Q171977) - Tercer unificador y fundador del Shogunato Tokugawa (período Edo).
4. Miyamoto Musashi (Q193344) - Legendario espadachín samurai y autor de 'El libro de los cinco anillos'.
5. Murasaki Shikibu (Q81731) - Dama de honor de la corte Heian, autora de 'La historia de Genji'.
6. Babur (Q797848) - Conquistador de Ferganá y fundador del Imperio Mogol en la India.
7. Akbar el Grande (Q8597) - Tercer emperador mogol, integrador religioso y político de la India.
8. Shah Jahan (Q83672) - Quinto emperador mogol, constructor del Taj Mahal en Agra.
9. Tamerlán (Q8462) - Conquistador turco-mongol, fundador del Imperio Timúrida en Samarcanda.
10. Emperador Kangxi (Q17790) - El emperador de más largo reinado de China (dinastía Qing).
11. Matsuo Bashō (Q5676) - Poeta maestro indiscutible del haiku japonés ('Sendas de Oku').
12. Katsushika Hokusai (Q5586) - Maestro del grabado ukiyo-e ('La gran ola de Kanagawa').
13. Sejong el Grande (Q37682) - Rey de Corea (dinastía Joseon) y creador del alfabeto Hangul.
14. Ibn Jaldún (Q9294) - Sabio magrebí, padre fundador de la sociología y la historiografía ('Muqaddimah').
15. Rumi (Q43347) - Poeta místico persa y maestro sufí universal ('Masnavi').
16. Hafez (Q6240) - Poeta lírico cumbre de la lengua y literatura persa de Shiraz.
"""

from scripts.batch_loader_utils import driver, ingest_batch

BATCH_NAME = "Lote 10: Japón Feudal, el Imperio Mogol, Persia y las Grandes Dinastías de Asia (~973 – 1849 d.C.)"

PEOPLE = [
    {
        "wikidata_id": "Q171411",
        "name": "Oda Nobunaga",
        "aliases": ["Nobunaga", "Oda Kippōshi", "Daimyo de Owari"],
        "principal_occupation": "Daimyo y primer unificador de Japón en el período Sengoku",
        "description": "Líder militar que inició la reunificación de Japón derrocando el shogunato Ashikaga, integrando armas de fuego y modernizando la táctica militar feudal.",
        "country": "JP",
        "city_born": "Nagoya",
        "birth": {"year": 1534, "month": 6, "day": 23, "precision": "day", "approximate": False},
        "death": {"year": 1582, "month": 6, "day": 21, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q187550",
        "name": "Toyotomi Hideyoshi",
        "aliases": ["Hideyoshi", "Hashiba Hideyoshi", "Taiko"],
        "principal_occupation": "General y segundo gran unificador del Japón feudal",
        "description": "Sucedió a Nobunaga, culminó la unificación política de Japón, impuso la separación de clases samurai y mandó erigir el castillo de Osaka.",
        "country": "JP",
        "city_born": "Nagoya",
        "birth": {"year": 1537, "month": 3, "day": 17, "precision": "day", "approximate": False},
        "death": {"year": 1598, "month": 9, "day": 18, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q171977",
        "name": "Tokugawa Ieyasu",
        "aliases": ["Ieyasu", "Matsudaira Takechiyo", "Tōshō Daigongen"],
        "principal_occupation": "Primer Shogun y fundador del Shogunato Tokugawa",
        "description": "Vencedor de la batalla de Sekigahara en 1600; instauró el régimen de los Tokugawa en Edo (Tokio), asegurando más de dos siglos y medio de estabilidad y paz.",
        "country": "JP",
        "city_born": "Okazaki",
        "birth": {"year": 1543, "month": 1, "day": 31, "precision": "day", "approximate": False},
        "death": {"year": 1616, "month": 6, "day": 1, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q193344",
        "name": "Miyamoto Musashi",
        "aliases": ["Shinmen Takezō", "Niten Dōraku", "Kensei"],
        "principal_occupation": "Espadachín, filósofo samurai, estratega y artista",
        "description": "El más célebre maestro de la espada de Japón, invicto en más de sesenta duelos a muerte; creador del estilo de dos espadas y autor de 'El libro de los cinco anillos'.",
        "country": "JP",
        "city_born": "Provincia de Harima",
        "birth": {"year": 1584, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "death": {"year": 1645, "month": 6, "day": 13, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q81731",
        "name": "Murasaki Shikibu",
        "aliases": ["Dama Murasaki", "Fujiwara no Kaoruko"],
        "principal_occupation": "Novelista, poetisa y dama de honor de la corte imperial Heian",
        "description": "Autora de 'La historia de Genji' (Genji Monogatari), monumental obra maestra de la corte de Kioto considerada la primera novela de la historia de la literatura universal.",
        "country": "JP",
        "city_born": "Kioto",
        "birth": {"year": 973, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "death": {"year": 1014, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q797848",
        "name": "Babur",
        "aliases": ["Zahir al-Din Muhammad", "Baber", "Emperador Babur"],
        "principal_occupation": "Conquistador y fundador del Imperio Mogol de la India",
        "description": "Príncipe timúrida de Asia Central que venció en la batalla de Panipat en 1526, conquistó Delhi y Agra y fundó la dinastía mogol, narrando su vida en el 'Baburnama'.",
        "country": "UZ",
        "city_born": "Andiján (Valle de Ferganá)",
        "birth": {"year": 1483, "month": 2, "day": 14, "precision": "day", "approximate": False},
        "death": {"year": 1530, "month": 12, "day": 26, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q8597",
        "name": "Akbar el Grande",
        "aliases": ["Jalal-ud-din Muhammad Akbar", "Akbar I"],
        "principal_occupation": "Tercer emperador del Imperio Mogol",
        "description": "Gobernante visionario que consolidó el Imperio Mogol en toda la India septentrional; instauró la tolerancia religiosa (Sulh-i-kul) y floreció las artes indo-persas.",
        "country": "PK",
        "city_born": "Umerkot",
        "birth": {"year": 1542, "month": 10, "day": 15, "precision": "day", "approximate": False},
        "death": {"year": 1605, "month": 10, "day": 27, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q83672",
        "name": "Shah Jahan",
        "aliases": ["Shahab-ud-din Muhammad Khurram", "Rey del Mundo"],
        "principal_occupation": "Quinto emperador del Imperio Mogol",
        "description": "Monarca bajo cuyo reinado la arquitectura mogola alcanzó su cenit absoluto, construyendo el célebre mausoleo Taj Mahal en Agra en memoria de su esposa Mumtaz Mahal.",
        "country": "PK",
        "city_born": "Lahore",
        "birth": {"year": 1592, "month": 1, "day": 5, "precision": "day", "approximate": False},
        "death": {"year": 1666, "month": 1, "day": 22, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q8462",
        "name": "Tamerlán",
        "aliases": ["Timur", "Timur Lenk", "Emir Timur"],
        "principal_occupation": "Conquistador turco-mongol y fundador del Imperio Timúrida",
        "description": "Líder militar que forjó un inmenso imperio desde Delhi hasta Anatolia, transformó Samarcanda en la capital del Renacimiento Timúrida y derrotó a otomanos y mamelucos.",
        "country": "UZ",
        "city_born": "Shahr-i Sabz (Kesh)",
        "birth": {"year": 1336, "month": 4, "day": 9, "precision": "day", "approximate": False},
        "death": {"year": 1405, "month": 2, "day": 18, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q17790",
        "name": "Emperador Kangxi",
        "aliases": ["Kangxi", "Xuanye", "Emperador Shengzu de Qing"],
        "principal_occupation": "Emperador de China (Dinastía Qing)",
        "description": "El monarca de más largo reinado de la historia china (61 años); expandió el imperio hasta el Tíbet y Mongolia, pacífico el sur e impulsó el célebre Diccionario de Kangxi.",
        "country": "CN",
        "city_born": "Pekín",
        "birth": {"year": 1654, "month": 5, "day": 4, "precision": "day", "approximate": False},
        "death": {"year": 1722, "month": 12, "day": 20, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q5676",
        "name": "Matsuo Bashō",
        "aliases": ["Bashō", "Matsuo Kinsaku", "Munefusa"],
        "principal_occupation": "Poeta maestro del haiku japonés y del haibun zen",
        "description": "Elevó el haiku a la categoría de alta poesía lírica y espiritual; sus diarios de viaje en prosa poética, singularmente 'Sendas de Oku' (Oku no Hosomichi), son cumbres de las letras niponas.",
        "country": "JP",
        "city_born": "Iga-Ueno",
        "birth": {"year": 1644, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "death": {"year": 1694, "month": 11, "day": 28, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q5586",
        "name": "Katsushika Hokusai",
        "aliases": ["Hokusai", "Gakyō Rōjin"],
        "principal_occupation": "Pintor y grabador japonés del género ukiyo-e",
        "description": "Gran maestro del grabado en madera del período Edo, inmortal por su serie 'Treinta y seis vistas del monte Fuji', que incluye la universalmente famosa estampa 'La gran ola de Kanagawa'.",
        "country": "JP",
        "city_born": "Edo (Tokio)",
        "birth": {"year": 1760, "month": 10, "day": 31, "precision": "day", "approximate": False},
        "death": {"year": 1849, "month": 5, "day": 10, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q37682",
        "name": "Sejong el Grande",
        "aliases": ["Rey Sejong", "Sejong de Joseon", "Yi Do"],
        "principal_occupation": "Cuarto monarca de la Dinastía Joseon de Corea",
        "description": "Rey sabio venerado por inventar y promulgar el alfabeto coreano nativo Hangul en 1446, impulsando el desarrollo científico, astronómico y agrícola de Corea.",
        "country": "KR",
        "city_born": "Hanseong (Seúl)",
        "birth": {"year": 1397, "month": 5, "day": 7, "precision": "day", "approximate": False},
        "death": {"year": 1450, "month": 4, "day": 8, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q9294",
        "name": "Ibn Jaldún",
        "aliases": ["Ibn Khaldun", "Abu Zayd Abd al-Rahman ibn Khaldun"],
        "principal_occupation": "Historiador, filósofo, jurista y sociólogo magrebí",
        "description": "Considerado el padre fundador de la historiografía científica y la sociología por su monumental 'Muqaddimah' (Prolegómenos), donde formuló la teoría de la cohesión social (asabiyyah).",
        "country": "TN",
        "city_born": "Túnez",
        "birth": {"year": 1332, "month": 5, "day": 27, "precision": "day", "approximate": False},
        "death": {"year": 1406, "month": 3, "day": 17, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q43347",
        "name": "Rumi",
        "aliases": ["Mawlana", "Yalal ad-Din Muhammad Rumi", "Mevlana"],
        "principal_occupation": "Poeta místico sufí, teólogo y jurista persa",
        "description": "El más influyente poeta espiritual de la lengua persa y de la tradición islámica sufí; autor del 'Masnavi' y maestro inspirador de la orden de los derviches giróvagos en Konya.",
        "country": "AF",
        "city_born": "Balkh",
        "birth": {"year": 1207, "month": 9, "day": 30, "precision": "day", "approximate": False},
        "death": {"year": 1273, "month": 12, "day": 17, "precision": "day", "approximate": False},
        "image_url": None,
    },
    {
        "wikidata_id": "Q6240",
        "name": "Hafez",
        "aliases": ["Hafez de Shiraz", "Khwaja Shams-ud-Din Muhammad Hafez-e Shirazi"],
        "principal_occupation": "Poeta lírico cumbre de la literatura persa",
        "description": "Célebre por su 'Diván' de gacelas que cantan al amor místico, la belleza y la libertad espiritual; figura venerada en todo el mundo iranio cuyas poesías marcaron a Goethe y Nietzsche.",
        "country": "IR",
        "city_born": "Shiraz",
        "birth": {"year": 1315, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "death": {"year": 1390, "month": 1, "day": 1, "precision": "year", "approximate": False},
        "image_url": None,
    },
]

CONNECTIONS = [
    # 1. Oda Nobunaga <-> Toyotomi Hideyoshi
    {
        "from_wikidata_id": "Q171411",
        "from_name": "Oda Nobunaga",
        "to_wikidata_id": "Q187550",
        "to_name": "Toyotomi Hideyoshi",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1568, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1582, "month": 6, "day": 21, "precision": "day", "approximate": False},
        },
        "location": {"name": "Castillo Azuchi / Kioto", "city": "Kioto", "country": "JP", "lat": 35.1558, "lng": 136.1394},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Unificación del Japón Feudal y Período Azuchi-Momoyama",
            "description": "Hideyoshi ascendió como principal general de confianza bajo el mando de Nobunaga en las campañas de reunificación feudal de Japón.",
        },
        "note": "Hideyoshi sirvió como general en jefe de Oda Nobunaga en la conquista del centro de Japón, vengando su muerte en Honnō-ji y consolidando el régimen Momoyama.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Per%C3%ADodo_Azuchi-Momoyama",
            "title": "Período Azuchi-Momoyama",
            "publisher": "Wikipedia",
            "citation": "Campañas de unificación militar de Nobunaga y ascenso de Hideyoshi.",
            "locator": "Historia",
        },
    },
    # 2. Toyotomi Hideyoshi <-> Tokugawa Ieyasu
    {
        "from_wikidata_id": "Q187550",
        "from_name": "Toyotomi Hideyoshi",
        "to_wikidata_id": "Q171977",
        "to_name": "Tokugawa Ieyasu",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1585, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1600, "month": 10, "day": 21, "precision": "day", "approximate": False},
        },
        "location": {"name": "Castillo de Osaka / Sekigahara", "city": "Osaka", "country": "JP", "lat": 34.6873, "lng": 135.5262},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Consejo de los Cinco Regentes y la Batalla de Sekigahara",
            "description": "Hideyoshi designó a Ieyasu como regente principal del Consejo de los Cinco Ancianos para gobernar Japón en nombre de su heredero.",
        },
        "note": "Tokugawa Ieyasu pactó alianza con Toyotomi Hideyoshi integrando el Consejo de los Cinco Regentes; tras la muerte de Hideyoshi, Ieyasu venció en Sekigahara.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Batalla_de_Sekigahara",
            "title": "Batalla de Sekigahara",
            "publisher": "Wikipedia",
            "citation": "Disputa sucesoria entre los partidarios de Hideyoshi y el ejército de Ieyasu.",
            "locator": "Antecedentes",
        },
    },
    # 3. Tokugawa Ieyasu <-> Miyamoto Musashi
    {
        "from_wikidata_id": "Q171977",
        "from_name": "Tokugawa Ieyasu",
        "to_wikidata_id": "Q193344",
        "to_name": "Miyamoto Musashi",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1600, "month": 10, "day": 21, "precision": "day", "approximate": False},
            "end": {"year": 1616, "month": 6, "day": 1, "precision": "day", "approximate": False},
        },
        "location": {"name": "Sekigahara / Castillo de Edo (Tokio)", "city": "Edo", "country": "JP", "lat": 35.6852, "lng": 139.7528},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Shogunato Tokugawa y la Vía del Samurai (Bushidō) en el Período Edo",
            "description": "Musashi combatió en Sekigahara y forjó su legendaria escuela marcial bajo el nuevo orden imperial pacificado por el Shogunato Tokugawa.",
        },
        "note": "Miyamoto Musashi participó en la histórica batalla de Sekigahara que encumbró a Ieyasu al poder supremo y desarrolló el estilo Niten Ichi-ryū en el periodo Edo.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Miyamoto_Musashi",
            "title": "Miyamoto Musashi",
            "publisher": "Wikipedia",
            "citation": "Participación en Sekigahara y servicio samurai en el Shogunato.",
            "locator": "Biografía",
        },
    },
    # 4. Tokugawa Ieyasu <-> Matsuo Bashō
    {
        "from_wikidata_id": "Q171977",
        "from_name": "Tokugawa Ieyasu",
        "to_wikidata_id": "Q5676",
        "to_name": "Matsuo Bashō",
        "type_id": "arts.collaborated_on_work",
        "from_role": "creator",
        "to_role": "writer",
        "period": {
            "start": {"year": 1603, "month": 3, "day": 24, "precision": "day", "approximate": False},
            "end": {"year": 1694, "month": 11, "day": 28, "precision": "day", "approximate": False},
        },
        "location": {"name": "Edo (Tokio) y el Santuario Nikkō Tōshō-gū", "city": "Nikkō", "country": "JP", "lat": 36.7580, "lng": 139.5989},
        "context": {
            "category": "work",
            "kind": "book",
            "name": "Cultura del Período Edo y la Paz Tokugawa (Sendas de Oku)",
            "description": "Bashō viajó por los caminos postales del shogunato y visitó el mausoleo de Ieyasu en Nikkō, inmortalizándolo en sus cuadernos de viaje.",
        },
        "note": "Matsuo Bashō rindió homenaje al fundador de la era Edo visitando el santuario Nikkō consagrado a Ieyasu, episodio plasmado en su obra cumbre 'Sendas de Oku'.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Matsuo_Bash%C5%8D",
            "title": "Matsuo Bashō",
            "publisher": "Wikipedia",
            "citation": "Peregrinación a Nikkō y la cultura literaria del Shogunato Tokugawa.",
            "locator": "Sendas de Oku",
        },
    },
    # 5. Matsuo Bashō <-> Katsushika Hokusai
    {
        "from_wikidata_id": "Q5676",
        "from_name": "Matsuo Bashō",
        "to_wikidata_id": "Q5586",
        "to_name": "Katsushika Hokusai",
        "type_id": "arts.collaborated_on_work",
        "from_role": "writer",
        "to_role": "creator",
        "period": {
            "start": {"year": 1689, "month": 5, "day": 16, "precision": "day", "approximate": False},
            "end": {"year": 1849, "month": 5, "day": 10, "precision": "day", "approximate": False},
        },
        "location": {"name": "Edo (Tokio) y la Ruta del Tōkaidō / Monte Fuji", "city": "Edo", "country": "JP", "lat": 35.3606, "lng": 138.7274},
        "context": {
            "category": "work",
            "kind": "book",
            "name": "Sendas de Oku y las Estampas del Mundo Flotante (Ukiyo-e del Monte Fuji)",
            "description": "Las dos máximas cumbres del arte visual y poético del período Edo, inspiradas en los mismos paisajes sagrados y sendas del archipiélago.",
        },
        "note": "Hokusai ilustró múltiples estampas y grabados ukiyo-e inspirados directamente en las poesías y caminos recorridos por Bashō en sus viajes por el Japón feudal.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Katsushika_Hokusai",
            "title": "Katsushika Hokusai",
            "publisher": "Wikipedia",
            "citation": "Estampas ukiyo-e y poesía paisajística del período Edo.",
            "locator": "Obra",
        },
    },
    # 6. Murasaki Shikibu <-> Confucio
    {
        "from_wikidata_id": "Q81731",
        "from_name": "Murasaki Shikibu",
        "to_wikidata_id": "Q4604",
        "to_name": "Confucio",
        "type_id": "arts.collaborated_on_work",
        "from_role": "writer",
        "to_role": "writer",
        "period": {
            "start": {"year": 990, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1014, "month": 1, "day": 1, "precision": "year", "approximate": False},
        },
        "location": {"name": "Palacio Imperial Heian-kyō (Kioto)", "city": "Kioto", "country": "JP", "lat": 35.0116, "lng": 135.7681},
        "context": {
            "category": "work",
            "kind": "book",
            "name": "Clásicos Confucianos y la Literatura de la Corte Imperial Heian (Genji Monogatari)",
            "description": "Murasaki Shikibu aprendió en secreto los clásicos chinos de Confucio, tejiendo la ética moral confuciana en la trama de 'La historia de Genji'.",
        },
        "note": "La Dama Murasaki dominó la literatura china clásica y las Analectas de Confucio impartidas a la nobleza cortesana Heian, asimilándolas en el Genji Monogatari.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Murasaki_Shikibu",
            "title": "Murasaki Shikibu",
            "publisher": "Wikipedia",
            "citation": "Educación en los clásicos chinos confucianos en la corte Heian.",
            "locator": "Juventud y educación",
        },
    },
    # 7. Tamerlán <-> Gengis Kan
    {
        "from_wikidata_id": "Q8462",
        "from_name": "Tamerlán",
        "to_wikidata_id": "Q720",
        "to_name": "Gengis Kan",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1206, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1405, "month": 2, "day": 18, "precision": "day", "approximate": False},
        },
        "location": {"name": "Samarcanda / Transoxiana", "city": "Samarcanda", "country": "UZ", "lat": 39.6542, "lng": 66.9597},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Imperios de las Estepas Euroasiáticas y el Linaje de los Grandes Kanes",
            "description": "Tamerlán legitimó sus conquistas como restaurador del Imperio mongol de Gengis Kan, asumiendo el título de Gurgan (yerno de la línea gengiskánida).",
        },
        "note": "Tamerlán basó la legitimidad imperial de sus conquistas en la restauración del imperio de Gengis Kan, desposando princesas gengiskánidas en Samarcanda.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Tamerl%C3%A1n",
            "title": "Tamerlán",
            "publisher": "Wikipedia",
            "citation": "Legitimación dinástica como heredero del Imperio gengiskánida.",
            "locator": "Ascenso al poder",
        },
    },
    # 8. Tamerlán <-> Ibn Jaldún
    {
        "from_wikidata_id": "Q8462",
        "from_name": "Tamerlán",
        "to_wikidata_id": "Q9294",
        "to_name": "Ibn Jaldún",
        "type_id": "personal.met",
        "period": {
            "start": {"year": 1400, "month": 12, "day": 1, "precision": "month", "approximate": False},
            "end": {"year": 1401, "month": 1, "day": 31, "precision": "month", "approximate": False},
        },
        "location": {"name": "Murallas y Campamento Real de Damasco", "city": "Damasco", "country": "SY", "lat": 33.5138, "lng": 36.2765},
        "context": {
            "category": "event",
            "kind": "personal.meeting",
            "name": "Encuentros y Diálogos Históricos de Damasco durante el Sitio Timúrida",
            "description": "Ibn Jaldún fue descolgado en una canasta de las murallas de Damasco para negociar durante semanas en la tienda del conquistador Tamerlán.",
        },
        "note": "Durante el asedio de Damasco en 1401, Ibn Jaldún y Tamerlán mantuvieron célebres coloquios filosóficos sobre el ascenso y caída de las civilizaciones.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Ibn_Jald%C3%BAn",
            "title": "Ibn Jaldún",
            "publisher": "Wikipedia",
            "citation": "Encuentro histórico con Tamerlán durante el asedio de Damasco.",
            "locator": "Últimos años",
        },
    },
    # 9. Tamerlán <-> Hafez
    {
        "from_wikidata_id": "Q8462",
        "from_name": "Tamerlán",
        "to_wikidata_id": "Q6240",
        "to_name": "Hafez",
        "type_id": "personal.met",
        "period": {
            "start": {"year": 1387, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1390, "month": 1, "day": 1, "precision": "year", "approximate": False},
        },
        "location": {"name": "Jardines de Shiraz", "city": "Shiraz", "country": "IR", "lat": 29.5918, "lng": 52.5837},
        "context": {
            "category": "event",
            "kind": "personal.meeting",
            "name": "Encuentro Legendario entre Tamerlán y Hafez en Shiraz",
            "description": "Tamerlán mandó llamar al anciano poeta Hafez a su corte militar en Shiraz para debatir el verso donde ofrecía Samarcanda por un lunar.",
        },
        "note": "Tamerlán interrogó en Shiraz al poeta Hafez sobre su famoso dístico lírico; la ingeniosa respuesta del vate conmovió al conquistador, quien le otorgó ricos presentes.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Hafez_de_Shiraz",
            "title": "Hafez de Shiraz",
            "publisher": "Wikipedia",
            "citation": "Audiencia histórica entre Tamerlán y Hafez en Shiraz.",
            "locator": "Biografía y leyendas",
        },
    },
    # 10. Tamerlán <-> Babur
    {
        "from_wikidata_id": "Q8462",
        "from_name": "Tamerlán",
        "to_wikidata_id": "Q797848",
        "to_name": "Babur",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1370, "month": 4, "day": 9, "precision": "day", "approximate": False},
            "end": {"year": 1530, "month": 12, "day": 26, "precision": "day", "approximate": False},
        },
        "location": {"name": "Samarcanda / Ferganá", "city": "Samarcanda", "country": "UZ", "lat": 39.6542, "lng": 66.9597},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Dinastía Timúrida de Samarcanda y Ferganá",
            "description": "Babur era tataranieto directo de Tamerlán por línea paterna y heredó el principado de Ferganá antes de conquistar el norte de la India.",
        },
        "note": "Babur reivindicó con orgullo su ascendencia directa de Tamerlán, asediando Samarcanda para recuperar el trono de sus antepasados timúridas.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Babur",
            "title": "Babur",
            "publisher": "Wikipedia",
            "citation": "Ascendencia timúrida de Babur y dinastía fundada por Tamerlán.",
            "locator": "Orígenes",
        },
    },
    # 11. Babur <-> Akbar el Grande
    {
        "from_wikidata_id": "Q797848",
        "from_name": "Babur",
        "to_wikidata_id": "Q8597",
        "to_name": "Akbar el Grande",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1526, "month": 4, "day": 21, "precision": "day", "approximate": False},
            "end": {"year": 1605, "month": 10, "day": 27, "precision": "day", "approximate": False},
        },
        "location": {"name": "Agra / Fatehpur Sikri / Delhi", "city": "Agra", "country": "IN", "lat": 27.1767, "lng": 78.0081},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Fundación y Consolidación del Imperio Mogol de la India",
            "description": "Akbar, nieto de Babur, transformó las conquistas iniciales de su abuelo en la estructura estatal más poderosa y estable de la historia del subcontinente.",
        },
        "note": "Akbar heredó y expandió los dominios fundados por su abuelo Babur en el norte de la India, estableciendo el apogeo imperial de la dinastía mogol.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Imperio_mogol",
            "title": "Imperio mogol",
            "publisher": "Wikipedia",
            "citation": "Fundación imperial por Babur y expansión consolidada por Akbar.",
            "locator": "Historia",
        },
    },
    # 12. Akbar el Grande <-> Shah Jahan
    {
        "from_wikidata_id": "Q8597",
        "from_name": "Akbar el Grande",
        "to_wikidata_id": "Q83672",
        "to_name": "Shah Jahan",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1556, "month": 2, "day": 14, "precision": "day", "approximate": False},
            "end": {"year": 1658, "month": 7, "day": 31, "precision": "day", "approximate": False},
        },
        "location": {"name": "Fuerte de Agra / Taj Mahal", "city": "Agra", "country": "IN", "lat": 27.1751, "lng": 78.0421},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Edad de Oro del Imperio Mogol y Construcción del Taj Mahal en Agra",
            "description": "Shah Jahan, nieto de Akbar, gobernó durante la era dorada arquitectónica del imperio forjado bajo la administración de su abuelo.",
        },
        "note": "Shah Jahan creció en la corte de su abuelo Akbar el Grande en Agra, heredando la opulencia y el mecenazgo artístico que culminó con el Taj Mahal.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Taj_Mahal",
            "title": "Taj Mahal",
            "publisher": "Wikipedia",
            "citation": "Apogeo constructivo mogol bajo Shah Jahan y legado de Akbar.",
            "locator": "Historia",
        },
    },
    # 13. Rumi <-> Gengis Kan
    {
        "from_wikidata_id": "Q43347",
        "from_name": "Rumi",
        "to_wikidata_id": "Q720",
        "to_name": "Gengis Kan",
        "type_id": "arts.collaborated_on_work",
        "from_role": "writer",
        "to_role": "creator",
        "period": {
            "start": {"year": 1215, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1273, "month": 12, "day": 17, "precision": "day", "approximate": False},
        },
        "location": {"name": "Balkh y Konya (Sultanato de Rum)", "city": "Konya", "country": "TR", "lat": 37.8746, "lng": 32.4932},
        "context": {
            "category": "work",
            "kind": "book",
            "name": "La Épica Mística del Masnavi y la Gran Diáspora de Corasmia y Konya",
            "description": "La invasión de Corasmia por las huestes de Gengis Kan forzó a la familia de Rumi a emigrar hacia Anatolia, donde compuso el 'Masnavi'.",
        },
        "note": "El avance militar de Gengis Kan precipitó el exilio de Rumi y su padre teólogo desde Asia Central hacia Konya, catalizando el nacimiento de su poesía sufí.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Rumi",
            "title": "Rumi",
            "publisher": "Wikipedia",
            "citation": "Huida de Balkh ante la invasión mongola y establecimiento en Konya.",
            "locator": "Biografía",
        },
    },
    # 14. Ibn Jaldún <-> Ibn Battuta
    {
        "from_wikidata_id": "Q9294",
        "from_name": "Ibn Jaldún",
        "to_wikidata_id": "Q7331",
        "to_name": "Ibn Battuta",
        "type_id": "arts.collaborated_on_work",
        "from_role": "writer",
        "to_role": "writer",
        "period": {
            "start": {"year": 1352, "month": 1, "day": 1, "precision": "year", "approximate": False},
            "end": {"year": 1406, "month": 3, "day": 17, "precision": "day", "approximate": False},
        },
        "location": {"name": "Fez / El Cairo", "city": "Fez", "country": "MA", "lat": 34.0181, "lng": -5.0078},
        "context": {
            "category": "work",
            "kind": "book",
            "name": "Crónicas Magrebíes del Sultanato Meriní de Fez y la Al-Muqaddimah",
            "description": "Ambos eruditos magrebíes sirvieron en la corte meriní de Fez; Ibn Jaldún cita y analiza los relatos de viaje de Ibn Battuta en su 'Muqaddimah'.",
        },
        "note": "Ibn Jaldún e Ibn Battuta coincidieron intelectualmente en la corte del sultán Abu Inan Faris en Fez; Ibn Jaldún examinó críticamente la 'Rihla' en sus escritos.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Ibn_Battuta",
            "title": "Ibn Battuta",
            "publisher": "Wikipedia",
            "citation": "Estancia en la corte de Fez y menciones en la obra de Ibn Jaldún.",
            "locator": "Redacción de la Rihla",
        },
    },
    # 15. Sejong el Grande <-> Zheng He
    {
        "from_wikidata_id": "Q37682",
        "from_name": "Sejong el Grande",
        "to_wikidata_id": "Q7333",
        "to_name": "Zheng He",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1418, "month": 9, "day": 9, "precision": "day", "approximate": False},
            "end": {"year": 1433, "month": 7, "day": 22, "precision": "day", "approximate": False},
        },
        "location": {"name": "Hanseong (Seúl) / Nankín", "city": "Seúl", "country": "KR", "lat": 37.5665, "lng": 126.9780},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Relaciones Tributarias y Cartografía Marítima entre la Dinastía Joseon y la Dinastía Ming",
            "description": "Sejong mantuvo intensas misiones diplomáticas con la corte imperial Ming durante los años de las expediciones oceánicas del almirante Zheng He.",
        },
        "note": "El reinado del rey Sejong en Joseon coincidió con el apogeo marítimo de la dinastía Ming liderado por Zheng He, compartiendo adelantos astronómicos y cartográficos.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Sejong_el_Grande",
            "title": "Sejong el Grande",
            "publisher": "Wikipedia",
            "citation": "Relaciones diplomáticas y científicas con la dinastía Ming.",
            "locator": "Política exterior",
        },
    },
    # 16. Emperador Kangxi <-> Kublai Kan
    {
        "from_wikidata_id": "Q17790",
        "from_name": "Emperador Kangxi",
        "to_wikidata_id": "Q7523",
        "to_name": "Kublai Kan",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1271, "month": 12, "day": 18, "precision": "day", "approximate": False},
            "end": {"year": 1722, "month": 12, "day": 20, "precision": "day", "approximate": False},
        },
        "location": {"name": "Ciudad Prohibida / Pekín", "city": "Pekín", "country": "CN", "lat": 39.9163, "lng": 116.3972},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Sucesión Imperial del Trono del Dragón de China (Dinastías Yuan y Qing en Pekín)",
            "description": "Ambos monarcas no han (mongol y manchú) asumieron el Mandato del Cielo como Hijos del Cielo desde la capital imperial de Pekín.",
        },
        "note": "El Emperador Kangxi veneró las ceremonias y el modelo administrativo imperial instituido desde Kublai Kan en la capital de Pekín, preservando la continuidad dinástica.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Emperador_Kangxi",
            "title": "Emperador Kangxi",
            "publisher": "Wikipedia",
            "citation": "Continuidad del mandato imperial y pacificación de Mongolia y China.",
            "locator": "Reinado",
        },
    },
    # 17. Tokugawa Ieyasu <-> Emperador Kangxi
    {
        "from_wikidata_id": "Q171977",
        "from_name": "Tokugawa Ieyasu",
        "to_wikidata_id": "Q17790",
        "to_name": "Emperador Kangxi",
        "type_id": "politics.same_government",
        "period": {
            "start": {"year": 1661, "month": 2, "day": 5, "precision": "day", "approximate": False},
            "end": {"year": 1716, "month": 1, "day": 1, "precision": "year", "approximate": False},
        },
        "location": {"name": "Puerto de Dejima / Nagasaki y Pekín", "city": "Nagasaki", "country": "JP", "lat": 32.7431, "lng": 129.8732},
        "context": {
            "category": "organization",
            "kind": "government",
            "name": "Comercio Marítimo y Diplomacia del Mar de China Oriental (Nagasaki y Pekín)",
            "description": "El Shogunato fundado por Ieyasu reguló el comercio exterior a través de Nagasaki expidiendo los certificados shinpai a los barcos del imperio de Kangxi.",
        },
        "note": "Las instituciones aduaneras del Shogunato Tokugawa en Nagasaki canalizaron un fluido intercambio de libros, plata y porcelana con el Imperio Qing de Kangxi.",
        "source": {
            "url": "https://es.wikipedia.org/wiki/Emperador_Kangxi",
            "title": "Emperador Kangxi",
            "publisher": "Wikipedia",
            "citation": "Comercio marítimo y relaciones con el Japón de los Tokugawa.",
            "locator": "Comercio",
        },
    },
]


if __name__ == "__main__":
    try:
        ingest_batch(BATCH_NAME, PEOPLE, CONNECTIONS)
    finally:
        driver.close()
