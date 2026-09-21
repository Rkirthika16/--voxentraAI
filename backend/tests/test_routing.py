from app.services.routing_service import routing_service


def test_department_routing(db_session):
    water_dept = routing_service.route_category_to_department(db_session, "Water")
    assert water_dept is not None
    assert "Water" in water_dept.name

    roads_dept = routing_service.route_category_to_department(db_session, "Roads")
    assert roads_dept is not None
    assert "Roads" in roads_dept.name

    other_dept = routing_service.route_category_to_department(db_session, "Unknown Category")
    assert other_dept is not None
