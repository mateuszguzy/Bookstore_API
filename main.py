import json
import requests
from flask import Flask, request
from flask_restful import Resource, Api, reqparse, fields, marshal_with, marshal


# ------ APP CONFIGURATION
app = Flask(__name__)
api = Api(app)
# --- DEFINE REQUEST PARSER TO EXTRACT FILTER PARAMETERS
parser = reqparse.RequestParser()
parser.add_argument("author", location="args")
parser.add_argument("from", location="args")
parser.add_argument("to", location="args")
parser.add_argument("acquired", location="args")


# ------ DEFINE BOOK ATTRIBUTES AND DATA TYPES
# --- FOR ALL THE BOOKS
resource_fields_for_all_books = {
        "id": fields.Integer,
        "title": fields.String,
        "authors": fields.List(fields.String),
        "acquired": fields.Boolean,
        "published_year": fields.String,
    }


# --- FOR A SINGLE BOOK
resource_fields_for_single_book = {
        "id": fields.Integer,
        "external_id": fields.String,
        "title": fields.String,
        "authors": fields.List(fields.String),
        "acquired": fields.Boolean,
        "published_year": fields.String,
        "thumbnail": fields.String,
    }


# ------ DEFINE API RESOURCES
# --- FOR ALL THE BOOKS
class AllBooks(Resource):
    """Returns data about all books present in book store database.

    Allows filtering results by author, year and if book is acquired by the book store or not."""
    # decorator formatting and validating data with previously defined dictionary
    @marshal_with(resource_fields_for_all_books)
    def get(self) -> list:
        # dictionary for possible arguments
        filters_parameters = dict()
        # check if any argument provided in URL has a value
        url_arguments = parser.parse_args()
        for arguments in url_arguments:
            if url_arguments[arguments] is None:
                continue
            else:
                # if argument has value pass it into the arguments dictionary
                filters_parameters[arguments] = url_arguments[arguments]
        # if arguments dictionary is not empty it means we need to filter the results
        if len(filters_parameters) != 0:
            filtered_books_list = filter_results(filters_parameters)
            return filtered_books_list
        # else return unfiltered books list
        all_books_in_database = read_books_data_from_json_file()
        return all_books_in_database


# --- FOR SINGLE BOOK
class SingleBook(Resource):
    """Allows showing, updating and deleting single book from database."""
    @staticmethod
    def get(book_id: str) -> dict:
        all_books_in_database = read_books_data_from_json_file()
        # in case user will invoke book with non-existing index return error message
        try:
            # due to Python counting from 0, need to lower the wanted index by 1
            book = all_books_in_database[int(book_id) - 1]
            return marshal(book, resource_fields_for_single_book)
        except IndexError:
            return {"no book with that index": 404}

    @marshal_with(resource_fields_for_single_book)
    def patch(self, book_id: str) -> dict:
        book_to_update = update_book(book_id=book_id, data_to_update_in_json=request.json, import_by="user")
        return book_to_update

    @staticmethod
    def delete(book_id: str) -> dict:
        all_books_in_database = read_books_data_from_json_file()
        for book in all_books_in_database:
            if str(book["id"]) == book_id:
                all_books_in_database.pop(all_books_in_database.index(book))
                save_data_to_json(all_books_in_database=all_books_in_database)
                return {"deleted": 200}
        return {"no book with that index": 404}


# --- FOR BOOKS IMPORT FROM GOOGLE API
class ImportBooks(Resource):
    """Handles importing books data from Google API.

    In case book is already present in book store database, it's data is updated.
    When book is not present, it's added to database."""
    @staticmethod
    def post() -> dict:
        api_link = "https://www.googleapis.com/books/v1/volumes?q="
        suffix = str()
        # check search parameters in request, if there is any "author" or "title" format API URL in correct way,
        # if there is "other" key:value pair in request pass it as default search term
        for attribute in request.json:
            if attribute == "title":
                suffix += "intitle:" + request.json[attribute].capitalize() + "+"
            elif attribute == "author":
                suffix += "inauthor:" + request.json[attribute].capitalize() + "+"
            else:
                api_link += request.json[attribute].capitalize() + "+"
        # formatting API URL so default search term is at the beginning and specific search terms are following
        api_link += suffix
        response = requests.get(api_link)
        # create a list of current books ids to compare with new data
        # if book is present, update info, if not add as a new position
        current_books_ids = list()
        all_books_in_database = read_books_data_from_json_file()
        for book in all_books_in_database:
            current_books_ids.append(book["external_id"])
        # # iterate through every book returned by Google API
        for book in response.json()["items"]:
            if book["id"] in current_books_ids:
                book_id = str(current_books_ids.index(book["id"]) + 1)
                update_book(book_id=book_id, data_to_update_in_json=book, import_by="import_request")
                continue
            # add currently added book to book_ids list, so it's also checked for duplicates
            current_books_ids.append(book["id"])
            new_book = extract_from_json(book)
            # next iterate through every dictionary containing book attribute and keywords
            # allowing extraction from API JSON file
            new_book["id"] = next_free_id()
            new_book["acquired"] = False
            # add new books to existing file
            all_books_in_database = read_books_data_from_json_file()
            all_books_in_database.append(marshal(new_book, resource_fields_for_single_book))
            save_data_to_json(all_books_in_database=all_books_in_database)
        return {"imported": 200}


# ------ DEFINE STATIC FUNCTIONS
def extract_from_json(book_data_in_json: dict) -> dict:
    """Extract data from Google API JSON file.

    In case of missing data in JSON assigns NoneType value to attribute."""
    new_book = dict()
    new_book["external_id"] = book_data_in_json["id"]
    new_book["title"] = book_data_in_json["volumeInfo"]["title"]
    # in some books in JSON file some data is missing, try/except handles those cases
    try:
        new_book["authors"] = book_data_in_json["volumeInfo"]["authors"]
    except KeyError:
        new_book["authors"] = None
    try:
        new_book["published_year"] = book_data_in_json["volumeInfo"]["publishedDate"].split("-")[0]
    except KeyError:
        new_book["published_year"] = None
    try:
        new_book["thumbnail"] = book_data_in_json["volumeInfo"]["imageLinks"]["smallThumbnail"]
    except KeyError:
        new_book["thumbnail"] = None
    return new_book


def read_books_data_from_json_file() -> list:
    """Open and read data from book store database file."""
    with open("books_data.json", mode="r") as file:
        all_books_in_database = json.load(file)
    return all_books_in_database


def update_book(book_id: str, data_to_update_in_json: dict, import_by: str) -> dict:
    """Takes care of updating data in book store database.

    Process data differently in case when update is ordered by user,
    and when it's automatically made during books update from Google API."""
    all_books_in_database = read_books_data_from_json_file()
    for book in all_books_in_database:
        if str(book["id"]) == book_id:
            book_to_update = book
            if import_by == "import_request":
                book_to_update.update(extract_from_json(data_to_update_in_json))
            elif import_by == "user":
                book_to_update.update(data_to_update_in_json)
            save_data_to_json(all_books_in_database=all_books_in_database)
            return book_to_update
        else:
            continue


def save_data_to_json(all_books_in_database: list) -> None:
    """Simply save data ino JSON file."""
    with open("books_data.json", mode="w") as file:
        json.dump(all_books_in_database, file, ensure_ascii=False)


def filter_results(filters_parameters: dict) -> list:
    """Filter books in book store database by parameters defined in URL."""
    all_books_in_database = read_books_data_from_json_file()
    # TODO - comment code and double check it
    # middle list used to pre-filter books
    middle_filtered_books_list = list()
    # final list of filtered books
    filtered_books_list = list()
    if filters_parameters["from"] == "":
        filters_parameters["from"] = "0"
    if filters_parameters["to"] == "":
        filters_parameters["to"] = "9999"
    if filters_parameters["author"] == "":
        middle_filtered_books_list = all_books_in_database
    else:
        for book in all_books_in_database:
            # some authors lists are empty, so it doesn't match the filter requirements
            if book["authors"] is None:
                book["authors"] = str()
            # check in authors list if any author covers filter query
            for author in book["authors"]:
                if filters_parameters["author"].lower() in author.lower():
                    middle_filtered_books_list.append(book)
                    break
    for book in middle_filtered_books_list:
        if book["published_year"] is None:
            book_published_year = "0"
        else:
            book_published_year = book["published_year"]
        if filters_parameters["from"] <= book_published_year <= filters_parameters["to"]:
            # check "acquired" parameter - it's easier to convert BOOL to STR then the other way around
            # some problems with comparing BOOL to BOOL
            # TODO - check if can be done better
            if filters_parameters["acquired"] == "":
                filtered_books_list.append(book)
            else:
                if filters_parameters["acquired"].lower() == str(book["acquired"]).lower():
                    filtered_books_list.append(book)
    return filtered_books_list


def next_free_id() -> int:
    """Look through every book in current book store database, and find one with the highest index.
    Return value bigger by one."""
    all_books_in_database = read_books_data_from_json_file()
    # in case that JSON file is empty, return index "1"
    try:
        return max(book["id"] for book in all_books_in_database) + 1
    except ValueError:
        return 1


api.add_resource(AllBooks, "/books")
api.add_resource(SingleBook, "/books/<book_id>")
api.add_resource(ImportBooks, "/import")


if __name__ == "__main__":
    app.run(debug=True)
