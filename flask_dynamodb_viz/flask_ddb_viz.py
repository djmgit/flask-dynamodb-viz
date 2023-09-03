
import json
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, parse_obj_as
from flask import Flask, render_template, send_file

class DDBTableInterface:
    def scan(*args, **kwargs):
        raise NotImplementedError("Method not implemented")

    def scan(*args, **kwargs):
        raise NotImplementedError("Method not implemented")

class DDBResourceInterface:
    class Table:
        name: str

    class Tables:
        def all():
            pass
    
    tables: Tables

class TableDescription(BaseModel):
    ItemCount: int
    TableArn: str
    TableName: str
    TableSizeBytes: int
    TableStatus: str


class DDBClientInterface:

    def describe_table(*args, **kwargs):
        raise NotImplementedError("Method not implemented")


class FlaskDDBVizConfig(BaseModel):
    ddb_resource: Any
    ddb_client: Any
    allowed_tables: Optional[List[str]] = None

def _big_scan(table: DDBTableInterface):
        scan_result = []
        last_evaluated_key = None

        while True:
            if last_evaluated_key is None:
                scanned_page = table.scan()
            else:
                scanned_page = table.scan(ExclusiveStartKey=last_evaluated_key)

            if scanned_page.get("Items") and len(scanned_page["Items"]) > 0:
                scan_result.extend(scanned_page["Items"])

            if "LastEvaluatedKey" not in scanned_page:
                break

            last_evaluated_key = scanned_page["LastEvaluatedKey"]

        return scan_result

def _get_all(table: DDBTableInterface):
    return _big_scan(table)

def _scan_page(table_name: str, last_evaluated_key: str, flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_resource: DDBResourceInterface = flask_ddb_viz_config.ddb_resource
    ddb_tables: List[DDBResourceInterface.Table] = ddb_resource.tables.all()
    table_names = [table.name for table in ddb_tables]
    if table_name not in table_names:
        return {"error": "Table does not exist"}, 404

    allowed_tables = flask_ddb_viz_config.allowed_tables
    if allowed_tables and table_name not in allowed_tables:
        return {"error": "Table cannot be shown"}, 403

    ddb_client: DDBClientInterface = flask_ddb_viz_config.ddb_client
    table_description: Dict[str, Any] = ddb_client.describe_table(TableName=table_name)
    table_description: TableDescription = parse_obj_as(TableDescription, table_description["Table"])

    last_evaluated_key = json.loads(last_evaluated_key) if last_evaluated_key else None

    ddb_table: DDBTableInterface = ddb_resource.Table(table_name)
    scanned_page: Dict[str, Any] = ddb_table.scan(ExclusiveStartKey=last_evaluated_key) if last_evaluated_key else ddb_table.scan()
    resultset: List[Dict[str, Any]] = scanned_page["Items"]
    return {"table_name": table_name, "items": resultset, "count": len(resultset),
            "total_item_count": table_description.ItemCount, "table_size_bytes": table_description.TableSizeBytes,
            "last_evaluated_key": scanned_page.get("LastEvaluatedKey", "")}

#def _get_table_from_factory(table_name: str, ddb_table_factory: DDBTableFactory) -> TableConfig:
    #return list(filter(lambda table_config: table_config.table_name == table_name, ddb_table_factory.tables))[0]

def _show_table_view(table_name: str, flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_resource: DDBResourceInterface = flask_ddb_viz_config.ddb_resource
    ddb_tables: List[DDBResourceInterface.Table] = ddb_resource.tables.all()
    table_names = [table.name for table in ddb_tables]
    if table_name not in table_names:
        return {"error": "Table does not exist"}, 404
    allowed_tables = flask_ddb_viz_config.allowed_tables
    if allowed_tables and table_name not in allowed_tables:
        return {"error": "Table cannot be shown"}, 403
    ddb_table: DDBTableInterface = ddb_resource.Table(table_name)
    resultset = _get_all(ddb_table)

    ddb_client: DDBClientInterface = flask_ddb_viz_config.ddb_client
    table_description: Dict[str, Any] = ddb_client.describe_table(TableName=table_name)
    table_description: TableDescription = parse_obj_as(TableDescription, table_description["Table"])

    return {"table_name": table_name, "items": resultset, "total_item_count": table_description.ItemCount,
            "table_size_bytes": table_description.TableSizeBytes}, 200

def _list_tables(flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_resource: DDBResourceInterface = flask_ddb_viz_config.ddb_resource
    ddb_tables: List[DDBResourceInterface.Table] = ddb_resource.tables.all()
    tables_names = [table.name for table in ddb_tables]
    allowed_tables = flask_ddb_viz_config.allowed_tables
    ddb_tables = ddb_tables if not allowed_tables else list(filter(lambda table: table in allowed_tables, ddb_tables))

    return {"items_count": len(tables_names), "tables": tables_names}, 200

def _describe_table(table_name: str, flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_client: DDBClientInterface = flask_ddb_viz_config.ddb_client
    return ddb_client.describe_table(TableName=table_name)
    

class FlaskDDBViz:
    
    def __init__(self, app: Optional[Flask]):
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        flask_ddb_viz_config: FlaskDDBVizConfig = app.config["FLASK_DDB_VIZ_CONFIG"]

        def show_table_view_wrapper(table_name: str):
            return _show_table_view(table_name, flask_ddb_viz_config)

        def list_tables_wrapper():
            return _list_tables(flask_ddb_viz_config)

        def describe_table_wrapper(table_name: str):
            return _describe_table(table_name, flask_ddb_viz_config)
        
        def scan_page(table_name: str, last_evaluated_key: str):
            return _scan_page(table_name, last_evaluated_key, flask_ddb_viz_config)
        
        def show_tables():
            ui_root = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui")
            ret = send_file(os.path.join(ui_root, "list.html"))
            ret.direct_passthrough = False
            return ret

        def static_files(directory, file):
            if directory not in ["js", "css"]:
                return "Unrecognised path", 404
            ui_root = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui")
            file_path = os.path.join(ui_root, directory, file)
            if not os.path.exists(file_path):
                return "File not found", 404
            ret = send_file(file_path)
            ret.direct_passthrough = False
            return ret
        

        app.add_url_rule("/ddb_table/<table_name>/records", view_func=show_table_view_wrapper, methods=["GET"])
        app.add_url_rule("/ddb_table/list", view_func=list_tables_wrapper, methods=["GET"])
        app.add_url_rule("/ddb_table/<table_name>/describe", view_func=describe_table_wrapper, methods=["GET"])
        app.add_url_rule("/ddb_table/<table_name>/records/<last_evaluated_key>", view_func=scan_page, methods=["GET"])
        app.add_url_rule("/ddb_table/ui/list", view_func=show_tables, methods=["GET"])
        app.add_url_rule("/ddb_table/static/<directory>/<file>", view_func=static_files, methods=["GET"])
