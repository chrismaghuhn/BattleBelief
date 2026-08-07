# Canonicalization Profile v1

Contract ID: `canonicalization-profile`
Contract version: `1`

Diese Datei definiert die Bytefolge, aus der Manifest-Digests entstehen.

1. Das Manifest muss zuerst gegen sein JSON-Schema validieren.
2. Die validierte Datenstruktur wird als JSON nach RFC 8785 (JSON
   Canonicalization Scheme, JCS) serialisiert.
3. Strings werden vor der Validierung nicht still normalisiert. Produzenten
   müssen Text in Unicode NFC erzeugen; ein Validator lehnt nicht-NFC-Strings
   ab.
4. JSON-Objekte mit mehrfach vorkommenden Schlüsseln, nicht endlichen Zahlen
   oder Werten außerhalb des vom Schema zugelassenen Bereichs sind ungültig.
5. YAML ist nur ein Autorenformat. Vor Hashbildung wird es mit einem
   Schema-aware Loader in dieselbe JSON-Datenstruktur überführt. Implizite
   Datums-, Boolean- oder Zahlkonvertierungen außerhalb des Schemas sind
   unzulässig.
6. SHA-256 wird über die UTF-8-Bytes der JCS-Ausgabe ohne BOM oder
   abschließenden Zeilenumbruch gebildet.
7. Der veröffentlichte Digest lautet `sha256:` gefolgt von 64
   kleingeschriebenen Hexadezimalzeichen.

Referenz: [RFC 8785 – JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785).

Die Implementierung und ihre Cross-Platform-Testvektoren sind ein M0-Artefakt.
Bis diese Tests bestehen, darf kein erzeugter Digest als Release-Claim
veröffentlicht werden.
