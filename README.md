# v1GCF_creator
Version 1 steam GCF gcache file generator/builder for creating gcache.gcf files for 2002/2003 beta steam client versions.

This tool is to be used for creating custom storage files for STMServer.  it will take a folder with files in it, a configuration file and some parameters and output a manifest(.manifest) and a storage, checksum and index file (.dat, .checksums and .index).
the generated files should be placed in the following stmserver directories to be picked up by the STMserver software:
- `.manifest` files go to `<stmserver root>\files\betamanifests\` (if the storage is for beta 1, aka 2002 steam; it should be placed in the subfolder name `\betamanifests\beta1\`.  for 2003 bet ssteam it goes directly into the `\betamanifests\` folder).
- `.dat, .checksums and .index` files go into `<stmserver root>\files\betastorages\` (if the storage is for beta 1, aka 2002 steam; it should be placed in the subfolder name `\betastorages\beta1\`.  for 2003 bet ssteam it goes directly into the `\betastorages\` folder).
Once all files are in place, you must make sure to add the new application to the CDR/content description record/second blob in order for the steam client to see it.  this readme does not go into the CDR format as it would need an entire wiki page for all the configurations.



**** NOTE ABOUT PMEIN1 FOLDER****
The files within 'pmein1' have been modified by pmein1 for his personally use.  it may or may not be useful to anyone else but was included for posterity.  there is no information given about his changes, it also uses a slightly older version of the generator code but may be more stable than the non-edited code.
