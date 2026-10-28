import logging
import json
from datetime import datetime, timezone
from uuid import uuid4
from modules.famous.models import PostFamous
from database.neo4j_service import driver

def save_new_famous(famous: PostFamous, country_code: str) -> tuple[int, str]:
    """
    Save in the database a new famous person using parameterized queries.
    Args:
        famous (PostFamous): The famous person to save
        country_code (str): The country code for the famous person
    Returns:
        tuple: A tuple containing the status code and a message
    """

    query = """
            CREATE (f:Famous:Person {
                id: $id,
                data: $data,
                revision: 1,
                created_at: $created_at,
                updated_at: $created_at,
                search_name: $real_name,
                real_name: $real_name,
                best_known_for: $best_known_for,
                profile_sumary_description: $profile_sumary_description,
                principal_occupation: $principal_occupation,
                other_occupations: $other_occupations,
                country: $country,
                city_born: $city_born,
                date_born: $date_born,
                date_died: $date_died,
                nicknames: $nicknames,
                image_url: $image_url,
                more_info_url: $more_info_url
            })
            RETURN elementId(f) as node_id, f.real_name as name
        """

    try:

        from modules.graph.models import PersonInput
        person = PersonInput(
            name=famous.real_name,
            aliases=famous.nicknames or [],
            description=famous.profile_sumary_description,
            country=country_code,
            city_born=famous.city_born,
            image_url=famous.image_url,
            birth={"year": famous.date_born.year, "month": famous.date_born.month,
                   "day": famous.date_born.day, "precision": "day"} if famous.date_born else None,
            death={"year": famous.date_died.year, "month": famous.date_died.month,
                   "day": famous.date_died.day, "precision": "day"} if famous.date_died else None,
        )

        records, summary, _ = driver.execute_query(
            query,
            id=str(uuid4()),
            data=json.dumps(person.model_dump(mode="json"), ensure_ascii=False),
            created_at=datetime.now(timezone.utc).isoformat(),
            real_name=famous.real_name,
            best_known_for=famous.best_known_for,
            profile_sumary_description=famous.profile_sumary_description,
            principal_occupation=famous.principal_occupation,
            other_occupations=famous.other_occupations,
            country=country_code,
            city_born=famous.city_born,
            date_born=famous.date_born,
            date_died=famous.date_died,
            nicknames=famous.nicknames,
            image_url=famous.image_url,
            more_info_url=famous.more_info_url,
            database_=os.getenv("NEO4J_DATABASE")
        )

        if not records:
            logging.error("No records returned - Creation failed")
            return 500, "Creation failed (no records returned)"

        if summary.counters.nodes_created < 1:
            logging.error(f"Metrics indicate no creation. Summary: {summary.counters}")
            return 500, "Creation failed (database metrics)"

        node_id = records[0]["node_id"]
        name = records[0]["name"]

        logging.info(f"Created Famous '{name}' with ID: {node_id} | "
                    f"Query time: {summary.result_available_after}ms")

        return 201, node_id

    except Exception as e:
        logging.error(f"Error creating famous person: {str(e)}")
        return 500, f"Error creating famous person: {str(e)}"

def check_famoues_exist(famoues_name: str) -> bool:
    """
    Check if a famous person exists in the database.
    Args:
        famoues_name (str): The name of the famous person to check
    Returns:
        tuple: A tuple containing the status code and a message
    """
    query = """
            MATCH (f:Famous {real_name: $real_name})
            RETURN elementId(f) as node_id, f.real_name as name
        """

    try:
        records, summary, _ = driver.execute_query(
            query,
            real_name=famoues_name,
            database_=os.getenv("NEO4J_DATABASE")
        )

        if not records:
            return False

        node_id = records[0]["node_id"]
        name = records[0]["name"]

        logging.info(f"Famous person '{name}' found with ID: {node_id} | "
                    f"Query time: {summary.result_available_after}ms")

        return True

    except Exception as e:
        logging.error(f"Error checking famous person existence: {str(e)}")
        return None
