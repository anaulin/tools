from textwrap import dedent

from book_sync.goodreads import parse_goodreads_csv

CSV = dedent(
    '''\
    Book Id,Title,Author,ISBN,ISBN13,My Rating,Date Read,Bookshelves,Exclusive Shelf,My Review
    111,2312,Kim Stanley Robinson,="",="9780316098120",4,2016/12/09,scifi,read,Loved it
    222,Some Unread Book,Jane Doe,="",="",0,,,to-read,
    333,A Reread,John Roe,="",="",5,2020/1/3,"favorites, scifi",currently-reading,
    '''
)


def test_parse_maps_fields(tmp_path):
    csv_file = tmp_path / "gr.csv"
    csv_file.write_text(CSV, encoding="utf-8")
    books = {b.fields["goodreads_id"]: b for b in parse_goodreads_csv(csv_file)}

    a = books["111"]
    assert a.fields["title"] == "2312"
    assert a.fields["status"] == "read"
    assert a.fields["rating"] == 4
    assert a.fields["finished"] == "2016-12-09"
    assert a.fields["isbn"] == "9780316098120"
    assert a.fields["shelves"] == ["scifi"]
    assert a.body == "Loved it"

    b = books["222"]
    assert b.fields["status"] == "want"  # to-read -> want
    assert b.fields["rating"] is None  # 0 -> None
    assert b.fields["isbn"] is None
    assert b.fields["finished"] is None

    c = books["333"]
    assert c.fields["status"] == "reading"  # currently-reading -> reading
    assert c.fields["finished"] == "2020-01-03"
    assert c.fields["shelves"] == ["favorites", "scifi"]
