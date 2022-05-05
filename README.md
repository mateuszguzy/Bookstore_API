# Bookstore API
Allows keeping track of bookstore inventory. 

Every book is defined by certain attributes e.g.:
```
{
    "id": 8,
    "external_id": "yHoHVDlB0qoC",
    "title": "The Return of the King",
    "authors": [
      "John Ronald Reuel Tolkien"
    ],
    "acquired": false,
    "published_year": "1997",
    "thumbnail": "http://books.google.com/books/content?
    id=yHoHVDlB0qoC&printsec=frontcover&img=1&zoom=5&source=gbs_api"
  }
```
Books data is acquired from [Google Books API](https://developers.google.com/books/docs/v1/using#WorkingVolumes).

All books data are stored and returned in JSON file.
## API Endpoints

### Get all the books from database
#### HTTP request
```
GET http://example.com/books
```

### Get certain books from database
All parameters MUST be present in request, but when certain parameter does not consider searched query, 
it's value should be left empty. 
#### HTTP request
```
GET http://example.com/books?author=<surname>&from=<year>&to=<year>&acquired=<true/false>
```
#### Query Parameters:
- author - name or surname of searched author,
- from - year FROM which books should be showed,
- to - year TO which books should be showed,
- acquired - state if searched books should be acquired by the bookstore or not

### Get single book from database 
#### HTTP request
```
GET http://example.com/books/<book_id>
```

### Update single book data
Every book can have any attribute updated, when it's stated in request body. 
#### HTTP request
```
PATCH http://example.com/books/<book_id>
```
#### Request body
```
{
  "acquired": true,
  "thumbnail": "http://some-other-thumbnail.com"
}
```

### Delete single book entry
#### HTTP request
```
DEL http://example.com/books/<book_id>
```

### Import books data from [Google Books API](https://developers.google.com/books/docs/v1/using#WorkingVolumes)
Allows to import any amount of books from [Google API](https://developers.google.com/books/docs/v1/using#WorkingVolumes),
by author, title or any keyword associated with searched book
#### HTTP request
```
POST http://example.com/import
```
#### Request body
```
{
  "author": "tolkien",
  "title": "return",
  "keyword": "king"
}
```