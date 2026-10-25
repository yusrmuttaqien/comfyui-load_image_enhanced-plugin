Load Image Enhanced flows

1. On user select from dropdown
   1. User select, node loads the image, update the filename field
2. On user upload
   1. User upload (select image), node loads the image (behind the scene, image is copied into `input` folder (CMIIM)), update the filename field
3. After MaskEditor save
   1. User save edit
      1. Server update the node
         1. Node perform actions:
            1. Transform the filename to prefix `clipspace/` and remove suffix
            2. Add the transformed to the dropdown values
               1. This should be instantly valid, even though added manually, in the filesystem, the clipspace is in the same correct path. Thus after reload, this should not cause error, right?
         2. `sync_maskeditor`, if
            1. on: sync the filename field to the clipspace filename
            2. off: do nothing
         3. Node don't perform actions:
