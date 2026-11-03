// Query name: ModelParams
// Requires: RepoRoot
//
// The one source every other query reads: the exported weights of the model
// the product serves. Parsing the file once here keeps the rest of the queries
// plain projections over a record.
//
// Right-click this query and untick "Enable load". It is a record, not a
// table, and it exists only to feed the others.

let
    Path = RepoRoot & "\ml\training\models\model_params.json",
    Source = Json.Document(File.Contents(Path))
in
    Source
