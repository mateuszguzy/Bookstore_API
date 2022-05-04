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
    """Returns data about all the books present in bookstore database.

    Allows filtering results by author, year and checks if book is acquired by the bookstore or not."""
    # decorator formatting and validating data with previously defined dictionary
    @marshal_with(resource_fields_for_all_books)
    def get(self) -> list:
        # parse URL request looking for arguments
        filters_parameters = parser.parse_args()
        # if any argument has None value, it means that non filtered list of books is required
        if None not in filters_parameters.values():
            filtered_books_list = filter_results(filters_parameters)
            return filtered_books_list
        all_books_in_database = read_books_data_from_json_file()
        return all_books_in_database


# --- FOR SINGLE BOOK
class SingleBook(Resource):
    """Allows showing, updating and deleting single book from database."""
    @staticmethod
    def get(book_id: str) -> dict:
        """Get one book with specified in request ID number, and return its data in JSON format."""
        all_books_in_database = read_books_data_from_json_file()
        # in case user will invoke book with non-existing index, return error message
        try:
            # due to Python counting from 0, need to lower the wanted index by 1
            book = all_books_in_database[int(book_id) - 1]
            return marshal(data=book, fields=resource_fields_for_single_book)
        except IndexError:
            return {"no book with that index": 404}

    @marshal_with(resource_fields_for_single_book)
    def patch(self, book_id: str) -> dict:
        """Update one specified book's information with data from request."""
        book_to_update = update_book(book_id=book_id, data_to_update_in_json=request.json, import_by="user")
        return book_to_update

    def delete(self, book_id: str) -> dict:
        """Delete one book specified by ID specified in request."""
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

    In case book is already present in bookstore database, it's data is updated.
    When book is not present, it's added to database."""
    def post(self) -> dict:
        api_link = "https://www.googleapis.com/books/v1/volumes?q="
        suffix = str()
        # check search parameters in request, if there is any "author" or "title" format API URL in correct way,
        # if there is "other" key:value pair in request pass it as default search term
        for parameter in request.json:
            if parameter == "title":
                suffix += "intitle:" + request.json[parameter].capitalize() + "+"
            elif parameter == "author":
                suffix += "inauthor:" + request.json[parameter].capitalize() + "+"
            else:
                api_link += request.json[parameter].capitalize() + "+"
        # formatting API URL so default search term is at the beginning and specific search terms are following
        api_link += suffix
        response = requests.get(api_link)
        # create a list of current books ids to compare with new data
        # if book is present update info, if not add as a new position
        current_books_ids = list()
        all_books_in_database = read_books_data_from_json_file()
        for book in all_books_in_database:
            current_books_ids.append(book["external_id"])
        # iterate through every book returned by Google API
        for book in response.json()["items"]:
            if book["id"] in current_books_ids:
                # due to Python counting from 0, need to add 1 to acquire wanted book ID
                book_id = str(current_books_ids.index(book["id"]) + 1)
                update_book(book_id=book_id, data_to_update_in_json=book, import_by="import_request")
                # when book is updated iterate to next book in JSON
                continue
            # add currently added book to current_books_ids list, so it's also checked for duplicates
            current_books_ids.append(book["id"])
            # extract book data from JSON and save it into bookstore database
            new_book = extract_from_json(book)
            new_book["id"] = next_free_id()
            # by default mark every imported book as not acquired
            new_book["acquired"] = False
            all_books_in_database = read_books_data_from_json_file()
            all_books_in_database.append(marshal(data=new_book, fields=resource_fields_for_single_book))
            save_data_to_json(all_books_in_database=all_books_in_database)
        return {"imported": 200}


# ------ DEFINE FUNCTIONS
def extract_from_json(book_data_in_json: dict) -> dict:
    """Extract data from Google API JSON file.

    In case of missing data in JSON assigns NoneType value to attribute."""
    new_book = dict()
    # those two parameters are always present in JSON, so no try/except is needed
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
    """Open and read data from bookstore database file."""
    with open("books_data.json", mode="r") as file:
        all_books_in_database = json.load(fp=file)
    return all_books_in_database


def update_book(book_id: str, data_to_update_in_json: dict, import_by: str) -> dict:
    """Takes care of updating data in bookstore database.

    Process data differently in case when update is ordered by user,
    and when it's automatically made during books update from Google API."""
    all_books_in_database = read_books_data_from_json_file()
    for book in all_books_in_database:
        # first search book that's going to be updated by its ID
        if str(book["id"]) == book_id:
            book_to_update = book
            # next distinguish if update is done by user or by data import from Google API
            # if by import firstly extract data from JSON and then update
            if import_by == "import_request":
                book_to_update.update(extract_from_json(book_data_in_json=data_to_update_in_json))
            # if by user update directly with data from request
            elif import_by == "user":
                book_to_update.update(data_to_update_in_json)
            save_data_to_json(all_books_in_database=all_books_in_database)
            return book_to_update
        else:
            continue


def save_data_to_json(all_books_in_database: list) -> None:
    """Simply save data ino JSON file."""
    with open("books_data.json", mode="w") as file:
        json.dump(obj=all_books_in_database, fp=file, ensure_ascii=False)


def filter_results(filters_parameters: dict) -> list:
    """Filter books in bookstore database by parameters defined in URL."""
    all_books_in_database = read_books_data_from_json_file()
    # middle list used to pre-filter books
    middle_filtered_books_list = list()
    # final list of filtered books
    filtered_books_list = list()
    # When empty value is provided for argument in URL, change them for filtering algorithm to work
    if filters_parameters["from"] == "":
        filters_parameters["from"] = "0"
    if filters_parameters["to"] == "":
        filters_parameters["to"] = "9999"
    # when there is no specified author, pass all authors (all books) to middle list
    if filters_parameters["author"] == "":
        middle_filtered_books_list = all_books_in_database
    # when author is specified, check all books in DB for match
    else:
        for book in all_books_in_database:
            # some books do not have authors, in that case assign empty string so algorithm can keep working
            if book["authors"] is None:
                book["authors"] = str()
            # check in authors list if any author covers filter query
            for author in book["authors"]:
                # when author is matched add book to middle list and break the for loop
                if filters_parameters["author"].lower() in author.lower():
                    middle_filtered_books_list.append(book)
                    break
    # next filtering is carried on middle list with initially filtered books
    for book in middle_filtered_books_list:
        # some books in database might not have assigned year of publication, in that case make it "0"
        # it will not be shown when user sends request with any specific years, but it will be shown when
        # no value for "from" and "to" parameters is provided
        if book["published_year"] is None:
            book_published_year = "0"
        else:
            book_published_year = book["published_year"]
        if filters_parameters["from"] <= book_published_year <= filters_parameters["to"]:
            # check "acquired" parameter - it's easier to convert BOOL to STR then the other way around
            # some problems with comparing BOOL to BOOL
            # when no value is passed in "acquired" parameter list all books, acquired or not
            if filters_parameters["acquired"] == "":
                filtered_books_list.append(book)
            else:
                if filters_parameters["acquired"].lower() == str(book["acquired"]).lower():
                    filtered_books_list.append(book)
    return filtered_books_list


def next_free_id() -> int:
    """Look through every book in current bookstore database, and find one with the highest index.
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
