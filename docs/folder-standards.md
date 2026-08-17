# Folder and naming standard

The folder generator creates a predictable project boundary before any inventory or conversion code
is allowed to touch files.

## Project names

Project names are normalized to lowercase kebab-case:

- use letters, numbers, and single hyphens;
- start and end with a letter or number;
- use a maximum of 64 characters after normalization;
- convert spaces and punctuation to hyphens;
- reject path separators, dot segments, and control characters.

Examples:

| Display name | Folder name |
| --- | --- |
| `Client Intake Q3` | `client-intake-q3` |
| `Research - Approved` | `research-approved` |

## Standard layout

Each project is created below one approved root:

```text
projects/
└── client-intake-q3/
    ├── incoming/   # newly received files
    ├── working/    # temporary or in-progress files
    ├── output/     # reviewed results
    └── archive/    # retained historical material
```

The generator creates directories with mode `750`, refuses a world-writable
approved root, and never overwrites an existing project. It returns an error
when a requested name could escape the approved root.

## Usage

The root can be supplied with `--root` or the `CCL_PROJECT_ROOT` environment
variable. Without either, the generator uses `./projects` relative to the
current working directory.

```bash
python folder_generator.py "Client Intake Q3" --root ./projects
```

The command prints only paths relative to the approved root. It does not delete
files, move files, or follow a project-name path supplied by the caller.
