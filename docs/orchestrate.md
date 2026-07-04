# Orchestrate

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae.

## Overview

Donec velit neque, auctor sit amet aliquam vel, ullamcorper sit amet ligula. Sed porttitor lectus nibh. Vivamus suscipit tortor eget felis porttitor volutpat.

## Pipelines

Curabitur aliquet quam id dui posuere blandit. Proin eget tortor risus.

```yaml
pipeline:
  name: lorem-ipsum
  schedule: "0 9 * * 1"
  steps:
    - find: lorem
    - transform: ipsum
    - enrich: dolor
    - signal: sit-amet
```

## Scheduling

Mauris blandit aliquet elit, eget tincidunt nibh pulvinar a. Nulla quis lorem ut libero malesuada feugiat.

```bash
lorem orchestrate run --pipeline ipsum
```

!!! tip "Lorem ipsum"
    Vivamus magna justo, lacinia eget consectetur sed, convallis at tellus. Cras ultricies ligula sed magna dictum porta.

## Error handling

Pellentesque in ipsum id orci porta dapibus. Donec sollicitudin molestie malesuada. Quisque velit nisi, pretium ut lacinia in, elementum id enim.