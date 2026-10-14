import struct

from cre.lucene import CODEC_MAGIC, read_codec_header, sizes_by_extension


def test_lecture_entete_dvm():
    codec = b"Lucene90DocValuesMetadata"
    raw = struct.pack(">I", CODEC_MAGIC) + bytes([len(codec)]) + codec + struct.pack(">I", 0) + bytes(range(16))
    header = read_codec_header(raw)
    assert header == {"codec": "Lucene90DocValuesMetadata", "version": 0, "segment_id": bytes(range(16)).hex()}


def test_tailles_par_extension():
    files = [("/x/_0_Lucene90_0.dvd", 100), ("/x/_0_Lucene90_0.dvm", 10), ("/x/_1_Lucene90_0.dvd", 50), ("/x/segments_3", 5)]
    assert sizes_by_extension(files) == {"dvd": 150, "dvm": 10, "segments": 5}
