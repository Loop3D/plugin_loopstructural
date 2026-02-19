# Changelog

## [0.1.13](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.12...v0.1.13) (2026-02-19)


### Bug Fixes

* handle geometry transformation result in qgsLayerToGeoDataFrame ([960ac02](https://github.com/Loop3D/plugin_loopstructural/commit/960ac025c2828560f0fde71f29554f02fd306a96))

## [0.1.12](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.11...v0.1.12) (2026-01-31)


### Bug Fixes

* abstract logging to debug manager, this could allow for file logging as well as console logging ([48a0ad5](https://github.com/Loop3D/plugin_loopstructural/commit/48a0ad5554c4070543eb035f17cf27f46e1377fc))
* add all m2l tools as toolbar buttons ([e153ec6](https://github.com/Loop3D/plugin_loopstructural/commit/e153ec60bf503844da3fbf7cdaf72cb274b80472))
* add automatic column guessing framework ([558e6fa](https://github.com/Loop3D/plugin_loopstructural/commit/558e6fadec0ec8f84842a1972ce11a183334bb75))
* add colour to surfaces ([7a95d32](https://github.com/Loop3D/plugin_loopstructural/commit/7a95d32824db6ac469965a05f5f2b657995232c8))
* add data converter widget and section thickness calculator ([ea99e14](https://github.com/Loop3D/plugin_loopstructural/commit/ea99e14809829fb670e55845c8e53c03e48e0c4d))
* add debug mode to sampler ([45f97d2](https://github.com/Loop3D/plugin_loopstructural/commit/45f97d2d4648d9e9eb50831cfa95dfa2675b3135))
* add geodataframetoproject for calculating contacts and guess columns./layers ([18c46ca](https://github.com/Loop3D/plugin_loopstructural/commit/18c46ca1d682942e4108cd24ee0f72e5c81b0bd2))
* add get debug mode ([ffa4dd4](https://github.com/Loop3D/plugin_loopstructural/commit/ffa4dd4aa8b68c78a36df922bd78c2feffeb6931))
* add helper to check if an attribute is none ([4221630](https://github.com/Loop3D/plugin_loopstructural/commit/42216302bb69d50afcbaff4c7183ec3918b78311))
* add image for basal contacts ([db4342f](https://github.com/Loop3D/plugin_loopstructural/commit/db4342f1d61353e93f1d88a92dfe2d3bffbb3f2e))
* add m2l icons for strat column ([2abf4b3](https://github.com/Loop3D/plugin_loopstructural/commit/2abf4b36a96eeab9a76fe63661570cae6e4b9d50))
* add message if no contacts found ([0704eb8](https://github.com/Loop3D/plugin_loopstructural/commit/0704eb853083560ca318db2c2a6d1e6c3c71bc80))
* add option to separate visualisation/modelling widget ([7e511a3](https://github.com/Loop3D/plugin_loopstructural/commit/7e511a33d73d084a2312e7bef8e636e613d2184d))
* add topology calculator widget ([c7d9b8e](https://github.com/Loop3D/plugin_loopstructural/commit/c7d9b8ed63fecd1c903b9fde4b9c7e7b8d132e3c))
* add widget for painting stratigraphic order from column onto shapefile ([ad69700](https://github.com/Loop3D/plugin_loopstructural/commit/ad697003a98bf8d7236914101e7e06fea569bf4f))
* add x/y to structure gdf ([3537cd3](https://github.com/Loop3D/plugin_loopstructural/commit/3537cd3c279b4978d3e8985ce6d5da952ce2ff79))
* adding helpers for stratigraphic column to data manager ([366e37f](https://github.com/Loop3D/plugin_loopstructural/commit/366e37fb26f5b78e61c932c4c945aac30378fa85))
* adding widget to paint stratigraphic order onto geology shapefile. For debugging stratraphic order ([6e2e202](https://github.com/Loop3D/plugin_loopstructural/commit/6e2e2021dc0bb378abd2c339d3f3bdeedec46130))
* allow different crs for input data and model. Force model crs to be projected ([1bef056](https://github.com/Loop3D/plugin_loopstructural/commit/1bef0567f9248847af6bd56edf8b0e4bbc606707))
* applying some copilot suggestions ([39437bd](https://github.com/Loop3D/plugin_loopstructural/commit/39437bd0504fefc4d4202f64db0c771e82d9a760))
* auto select sampler or decimator for line/point data ([e831747](https://github.com/Loop3D/plugin_loopstructural/commit/e831747fcb809b0c5e42fedc36e69b05d9eb6301))
* avoid adding null units to stratigraphic column ([08320af](https://github.com/Loop3D/plugin_loopstructural/commit/08320af67620589d737457a61d00574ad635d667))
* block model from being built with default bounding box. ([42f175d](https://github.com/Loop3D/plugin_loopstructural/commit/42f175d6ca01b19d0de8628d563b2f96a1167b86))
* bump loopstructural version ([dea0075](https://github.com/Loop3D/plugin_loopstructural/commit/dea00755703cfcd240538973d1aa3c9514bcaef6))
* change basal contacts from processing call to a shared api ([2d13552](https://github.com/Loop3D/plugin_loopstructural/commit/2d135520f112dfac021f22f99acd4322e9b4ff2a))
* close ml2 widgets when tool has been run successfully ([038a009](https://github.com/Loop3D/plugin_loopstructural/commit/038a009c00577e50729c1a689f772b5d151d7fde))
* close topo calc when finished ([2e78c33](https://github.com/Loop3D/plugin_loopstructural/commit/2e78c3399039c952315c77796fb646a4c25b447d))
* colour faults using stratigraphic column ([9eb95fd](https://github.com/Loop3D/plugin_loopstructural/commit/9eb95fdd9eeb55afa3696fe7a5906b9eedb104ab))
* connect up thickness calc ([01dfbd4](https://github.com/Loop3D/plugin_loopstructural/commit/01dfbd4e669b53ac11f42b03bc48f75d20febb27))
* convert unit_name_field to 'UNITNAME' ([351a96a](https://github.com/Loop3D/plugin_loopstructural/commit/351a96a6a040d8e996ce1d17d3f40be77177c867))
* debug mode to thickness calc ([a9ef752](https://github.com/Loop3D/plugin_loopstructural/commit/a9ef752adda830560f2116234e557bd869fd4dac))
* decouple surfaces from model if model has been reset. ([ed015c3](https://github.com/Loop3D/plugin_loopstructural/commit/ed015c3374a708efe752db82e4829abf0c078415))
* dont run user define sorter, there is nothing to run! ([7d6cbb3](https://github.com/Loop3D/plugin_loopstructural/commit/7d6cbb3a38b7be0395231338e8f5f5df862f6066))
* find layer can work with other layer types ([dc6730a](https://github.com/Loop3D/plugin_loopstructural/commit/dc6730a0434acfc5ce54760190b43df6c836e71d))
* get list of units from datamanager for extracting contacts out ([64952ea](https://github.com/Loop3D/plugin_loopstructural/commit/64952ea35064b8dadbe1b7fe17e346cc689e07fb))
* get logging from m2l ([cae7e21](https://github.com/Loop3D/plugin_loopstructural/commit/cae7e2172d8afa58460afa016302773c16c6d67f))
* guess layers/colum names ([00a4f89](https://github.com/Loop3D/plugin_loopstructural/commit/00a4f89fafefd4dff4ddf51c9ebc8393dd8edc72))
* guess sorter columns/layers ([64be0b8](https://github.com/Loop3D/plugin_loopstructural/commit/64be0b894ec58bb0e5f146a62b2ff439914b8ab4))
* incorrect field name ([70fdbbb](https://github.com/Loop3D/plugin_loopstructural/commit/70fdbbbad8f5b030d73a3f40223cdb5508ec4ad6))
* linting ([bdeccb8](https://github.com/Loop3D/plugin_loopstructural/commit/bdeccb810d89dcd20feb833578d8fe747dd96eda))
* loopstructural/map2loop share the same stratigraphic column widget/backend ([909610d](https://github.com/Loop3D/plugin_loopstructural/commit/909610d4605a5deb7dca63bcccbc723883d53f1b))
* mapping stratigraphic column sorters to qgis fields/layers ([b443e29](https://github.com/Loop3D/plugin_loopstructural/commit/b443e29688cfef9cb1ed38439b137d4b6fbd927f))
* pass data manager to all widgets ([2f695b0](https://github.com/Loop3D/plugin_loopstructural/commit/2f695b0c1ba52f22feb13dc109d50a029eec94db))
* pass data manager to widgets ([7b585b4](https://github.com/Loop3D/plugin_loopstructural/commit/7b585b42419854dc0c4a126081615d8624eee08d))
* Persist and auto-guess layer/field selections across map2loop and LoopStructural setup widgets ([#73](https://github.com/Loop3D/plugin_loopstructural/issues/73)) ([6dec6e2](https://github.com/Loop3D/plugin_loopstructural/commit/6dec6e2a0172b2a389bab04c50895fec57460d54))
* remove bb  steps from bb widget ([64d5c00](https://github.com/Loop3D/plugin_loopstructural/commit/64d5c002dbb19157a5f7b82867d4b5ecd65dde06))
* remove QgsProxyModel from .ui file and move to .py file ([bd81685](https://github.com/Loop3D/plugin_loopstructural/commit/bd816859742a18b0e4b6e60797a5e2996761fd98))
* remove search radius ([7f15d91](https://github.com/Loop3D/plugin_loopstructural/commit/7f15d9131ca7337acb51ac23213d362b7b77b570))
* remove stratigraphic column layers ([6e05ec7](https://github.com/Loop3D/plugin_loopstructural/commit/6e05ec78327e0990ac891caf5858f29cc6fc9a18))
* rename unit_name_column to  unit_name_field ([24cc539](https://github.com/Loop3D/plugin_loopstructural/commit/24cc539bbd5a59e09410fea7f3846abe73e71cbf))
* set calculator params to correct argument names ([8266dca](https://github.com/Loop3D/plugin_loopstructural/commit/8266dcacfb3b4fd734057019df13281b1dae66c8))
* set default sorter to age based ([3503c7e](https://github.com/Loop3D/plugin_loopstructural/commit/3503c7e40cf69ec610429f72e2357bba9a0cadc3))
* store location tracking and lines for thickness calculators ([06e586f](https://github.com/Loop3D/plugin_loopstructural/commit/06e586fb70c61b81b083d79b91bc0272984b6a7c))
* sync fault topo calculator with the data manager. Use the same layers and update the adjacency graph ([76aef57](https://github.com/Loop3D/plugin_loopstructural/commit/76aef578279727a71376ed822e3235880ea6d13c))
* update logger to make threadsafe in qgis ([fa84e27](https://github.com/Loop3D/plugin_loopstructural/commit/fa84e27c671641784e8f7217833bc675332b12b7))
* update strat column thickness after thickness calc ([9c6d4a9](https://github.com/Loop3D/plugin_loopstructural/commit/9c6d4a99ff2458b8f2f2d1fb7778c2cc7c6bb9ac))
* update stratigraphic column with calculated thicknesses ([56ceb77](https://github.com/Loop3D/plugin_loopstructural/commit/56ceb77a8d5fcd5f2da7d6b7b67f0193da7e0acb))
* update stratigraphic unit to prevent missing widget error ([5fba7c8](https://github.com/Loop3D/plugin_loopstructural/commit/5fba7c899143f929b1ffc771364a42c3a8c712a9))
* update thickness widget ([29caccf](https://github.com/Loop3D/plugin_loopstructural/commit/29caccfa41fec276d3577db321ad8ad8cd003638))
* update thicknesses in stratigraphic colum after thickness calculator runs ([d53fa46](https://github.com/Loop3D/plugin_loopstructural/commit/d53fa46f2b28e7936066822730a70d41d258fa70))
* updating unload to prevent error when missing dock widgets ([2ec3fcd](https://github.com/Loop3D/plugin_loopstructural/commit/2ec3fcd1b19fe6e475881e10ddf28eb23d8ae432))
* use api for samplers, sorters and calculators ([b5a3532](https://github.com/Loop3D/plugin_loopstructural/commit/b5a35329f4b57b9cf2cfc183f9b8b85a7d07cb27))
* use debug manager logger and avoid adding color twice for strat surfaces ([9955147](https://github.com/Loop3D/plugin_loopstructural/commit/995514743bde7a45576e1856f82b5cc472df5ebc))
* use layer crs for sampler ([e5125bb](https://github.com/Loop3D/plugin_loopstructural/commit/e5125bbd72d12a1ca65b6fad2540cc3a0c3996b0))
* use logger instead of print ([2d2f848](https://github.com/Loop3D/plugin_loopstructural/commit/2d2f8485fe5e5d14405b81fa02d3fd0c68c544ee))
* use options manager for getting debug mode ([f21e4c8](https://github.com/Loop3D/plugin_loopstructural/commit/f21e4c8d9eb9db3ac717eb4db911888db836bab4))


### Documentation

* remove copilot doc ([7abe2bf](https://github.com/Loop3D/plugin_loopstructural/commit/7abe2bf95b189b019bac109ddbbc28e90230788c))

## [0.1.11](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.10...v0.1.11) (2025-09-08)


### Bug Fixes

* use python 3.9 compatible typehint ([f52b729](https://github.com/Loop3D/plugin_loopstructural/commit/f52b7292e054d8deacc2934e33be4d831785d512))
* use python 3.9 compatible typehint ([e3c6b48](https://github.com/Loop3D/plugin_loopstructural/commit/e3c6b48e58363a34ece61d2c27e26defc34839af))

## [0.1.10](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.9...v0.1.10) (2025-09-08)


### Bug Fixes

* add edge visibility toggle and line width control in ObjectPropertiesWidget ([8bf43e1](https://github.com/Loop3D/plugin_loopstructural/commit/8bf43e1311d5c967c6113239d84fd36b34fd21b3))
* add geopandas ([62a8124](https://github.com/Loop3D/plugin_loopstructural/commit/62a8124c06a083e3748706c588016aceb7bc8861))
* add histogram for scalar value, allow selecting scalar, choose to colour with scalar or with solid colour ([ea0aefc](https://github.com/Loop3D/plugin_loopstructural/commit/ea0aefc6b67e200bb2e4e4f157a25624c161c392))
* add layer from qgis to visualisation ([50cec1b](https://github.com/Loop3D/plugin_loopstructural/commit/50cec1bd9772499c5484f700d6bf8d569eb9a818))
* adding export of scalar field value to qgis vector pointset ([037d50f](https://github.com/Loop3D/plugin_loopstructural/commit/037d50f980dfa18d818f4d42e829f6ac50b308dd))
* allow all pv objects to be loaded ([742508e](https://github.com/Loop3D/plugin_loopstructural/commit/742508e63adabd9f9620595ded28a68ef8ee2c24))
* apply colourmap change and refactored actor/mapper update into single function ([352f5b1](https://github.com/Loop3D/plugin_loopstructural/commit/352f5b1b2fc50e1f3717f58ea737bde2d9b40b07))
* evalute feature onto vtk grid ([33b2967](https://github.com/Loop3D/plugin_loopstructural/commit/33b29670aa31d92bbfb8bd65cb2ec070522fd8dc))
* lint ([efec3ab](https://github.com/Loop3D/plugin_loopstructural/commit/efec3ab55774dbd0bf41798457b2662162b636e8))
* linting ([dc7d8f2](https://github.com/Loop3D/plugin_loopstructural/commit/dc7d8f24c2ec55a1de780cdb4f4bec9b8e7be9a6))
* make fold plunge/azi attributes of panel for easy access ([ccc03b9](https://github.com/Loop3D/plugin_loopstructural/commit/ccc03b99238dbaf6968ca56957bb7052dd37a398))
* put all feature options in QgsCollapsibleGroupBox ([08a50db](https://github.com/Loop3D/plugin_loopstructural/commit/08a50db9b8d37157462817779045e4be83993bf9))
* remove feature data from data manager when its deleted ([3ce70a1](https://github.com/Loop3D/plugin_loopstructural/commit/3ce70a17bcf740c30c6e4001e4896e179cdce8ff))
* remove print statements, rescale z for data to be in real coordinates ([29abb3e](https://github.com/Loop3D/plugin_loopstructural/commit/29abb3ebd11cd74e105a6440f52032fea88eb69b))
* streamline color handling and scalar updates in ObjectPropertiesWidget ([165f25f](https://github.com/Loop3D/plugin_loopstructural/commit/165f25fcebf6a605bdb1fb89ce94ac8fa9b0e250))
* update viewer to store meshes and a reference to actors. ([1dc4b2f](https://github.com/Loop3D/plugin_loopstructural/commit/1dc4b2f65fa3cdb3547feee743839fe16a7fa8ff))
* updating stratigraphic column, need update loopstructural. ([2572749](https://github.com/Loop3D/plugin_loopstructural/commit/2572749f858158503292f1b7b5c520053ecf5788))
* upgrade loopstructural requirement ([c905dda](https://github.com/Loop3D/plugin_loopstructural/commit/c905dda4448183fc0ad68bae7bfe5fac84635b02))
* use active_scalars_name to prefile scalars kwarg ([8124f36](https://github.com/Loop3D/plugin_loopstructural/commit/8124f36adab8eff9aa596b529dfe7e3af94b7e9b))
* use z coordinate if it exists for all manually added features ([5561ded](https://github.com/Loop3D/plugin_loopstructural/commit/5561ded0cc3772e16180c35c1d8275f17b7a09fe))
* uses the meshes dictionary for export ([437817c](https://github.com/Loop3D/plugin_loopstructural/commit/437817c3415dafd02b11a5ca6c99f4fa9775881b))

## [0.1.9](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.8...v0.1.9) (2025-09-03)


### Bug Fixes

* add delete feature option ([a194636](https://github.com/Loop3D/plugin_loopstructural/commit/a194636eb3885d1213b9548f2c01d749d37ad72f))
* add logging for when project is cleared ([80f6762](https://github.com/Loop3D/plugin_loopstructural/commit/80f67625d47003e958a5aea59efed926af4f16d4))
* add loopsolver for inequalities ([5f6ebee](https://github.com/Loop3D/plugin_loopstructural/commit/5f6ebee505da75568b2980647f873d9bc54a5e30))
* catch dem missing error ([14fcc9e](https://github.com/Loop3D/plugin_loopstructural/commit/14fcc9e9c5c04ce3ea30d7c3e5034355771f3cd9))
* remove feature selector from foliation dialog ([d0f3502](https://github.com/Loop3D/plugin_loopstructural/commit/d0f35022dc2283bc8b03654531549e3006199871))
* reset plugin when new project created ([5a3d33c](https://github.com/Loop3D/plugin_loopstructural/commit/5a3d33cc0eab3c35f1097e34931f07d878b4a12d))
* set dem on load ([128f1da](https://github.com/Loop3D/plugin_loopstructural/commit/128f1da65a7a2d20e4fbdc9b1be0332336c40977))
* upgrade ls ([83850ee](https://github.com/Loop3D/plugin_loopstructural/commit/83850eee8817e16f1bd54193ec8939752b7463e6))

## [0.1.8](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.7...v0.1.8) (2025-08-26)


### Bug Fixes

* abstract data table into separate class ([3a253a6](https://github.com/Loop3D/plugin_loopstructural/commit/3a253a6b4b7f9f2cf401ba0a682be727fc1aadce))
* add AddFaultDialog and AddFoldFrameDialog for fault and fold frame creation ([367c252](https://github.com/Loop3D/plugin_loopstructural/commit/367c252697fe80d8de388ba9446e8d1d94874e51))
* add convert from feature to structural frame button ([7cfd1ad](https://github.com/Loop3D/plugin_loopstructural/commit/7cfd1ade0e74c6bacc0e8b527d05175081dec274))
* add data table to feature details panel ([8948cde](https://github.com/Loop3D/plugin_loopstructural/commit/8948cded69bb1eae51882e7a7605b703ba29eaef))
* add pyqtgraph ([67b06ba](https://github.com/Loop3D/plugin_loopstructural/commit/67b06ba3a5cd29f409b2c15b956f83f95c7bdddb))
* add unconformity button ([7b78503](https://github.com/Loop3D/plugin_loopstructural/commit/7b7850366e5032a001b7231f6d445d5c1e4380de))
* adding splot dialog ([a027910](https://github.com/Loop3D/plugin_loopstructural/commit/a0279101cdd44c522a419e07d19526ad46f2771b))
* convert from structural frame to fold frame ([5c9dfe7](https://github.com/Loop3D/plugin_loopstructural/commit/5c9dfe74480962d68bc48e503a453ef8ba43e59c))
* copy data to new feature name if name changes ([136a6a5](https://github.com/Loop3D/plugin_loopstructural/commit/136a6a5fef1bcb2d8e9122cb57d1a03d05185340))
* dip direction now works ([a422032](https://github.com/Loop3D/plugin_loopstructural/commit/a42203287b0443e93d4b68432c0fba98c740d50f))
* don't try and add id to widget ([4286e07](https://github.com/Loop3D/plugin_loopstructural/commit/4286e07c10fc95075a68c2b4c00e4ab762b779c9))
* ensure geoh5py try catch actually has import in the block ([4c71c6c](https://github.com/Loop3D/plugin_loopstructural/commit/4c71c6c9b36d117c81017047417b89269e145bb9))
* integrate layer selection table into add foliation dialog ([0bcc4da](https://github.com/Loop3D/plugin_loopstructural/commit/0bcc4dacb1e6ebb1882dd2370f0b2ca52ecca8cf))
* linting ([7d8d47a](https://github.com/Loop3D/plugin_loopstructural/commit/7d8d47a621373cf54a5ef36f22868ba62eab1e29))
* move model_setup to own submodule. Change from add fold frame to just foliation ([ee7e8cc](https://github.com/Loop3D/plugin_loopstructural/commit/ee7e8ccb2a976c7bb724e18e7f306cac4480c3ec))
* pass pitch to fault model ([d32d962](https://github.com/Loop3D/plugin_loopstructural/commit/d32d96225af1f08103279bee4b22395110c37dcf))
* remove layer name from delete button ([422bc14](https://github.com/Loop3D/plugin_loopstructural/commit/422bc1476f84916e55382aefe579194344f4a1aa))
* replace items table with layer selection table in base feature details panel ([c4b649c](https://github.com/Loop3D/plugin_loopstructural/commit/c4b649c76a48855f4c371146ffa59edeab30ecb3))
* upgrade LS ([5016afb](https://github.com/Loop3D/plugin_loopstructural/commit/5016afbde1a63ca997aa7085d6fa05731280cac0))
* use data arg, not specifc name ([a6d70ec](https://github.com/Loop3D/plugin_loopstructural/commit/a6d70ec0a2d912f3c2e6363f40d71cdf1f9a6594))

## [0.1.7](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.6...v0.1.7) (2025-07-30)


### Bug Fixes

* add abutting relationships to model ([65b91cd](https://github.com/Loop3D/plugin_loopstructural/commit/65b91cd5d916562ad9a99aeb17ba2a61ae2f2b77))
* add axes to plot ([bb19086](https://github.com/Loop3D/plugin_loopstructural/commit/bb19086aac2e72e858e0c00058cddc426158424b))
* add bounding box outline instead of solid box ([e917539](https://github.com/Loop3D/plugin_loopstructural/commit/e9175391b35b00b50105b348397a4c5c1d9024da))
* add clear stratigraphic column ([6ee278b](https://github.com/Loop3D/plugin_loopstructural/commit/6ee278be9a21185eda443f3681f749f9c0341b27))
* add dem ([f40aa17](https://github.com/Loop3D/plugin_loopstructural/commit/f40aa17ddbfc135b86fe1b5d63bedd165d98fe2b))
* add feature detail panels ([ac7070e](https://github.com/Loop3D/plugin_loopstructural/commit/ac7070ecc7aafe98d2802903257c3500a5ecd6d3))
* add feature list widget. Shows all features in model for the visualiser ([d4a0312](https://github.com/Loop3D/plugin_loopstructural/commit/d4a031281ddb82c3bb4b76a363d4f7cc44e0c0bc))
* add instructions labels to fault adjacency and stratigraphic units tables ([aca081c](https://github.com/Loop3D/plugin_loopstructural/commit/aca081cbf0d08c3fd2200bdffa2d7d024b24c365))
* add key mapping for view/delete ([dd06eb3](https://github.com/Loop3D/plugin_loopstructural/commit/dd06eb32bab8f14d1b6c28363d3f3092a19b75e7))
* add loopstructural log messages to qgis plugin ([c33cdec](https://github.com/Loop3D/plugin_loopstructural/commit/c33cdece9080331afe6bc0c1d0b65a0f4098ca1b))
* add meshio as requirement ([65de3be](https://github.com/Loop3D/plugin_loopstructural/commit/65de3be544957bee87b22b6bb547d98cfef70076))
* add option to use shapefile z values instead of dem when the shapefile has a 3D element ([d231204](https://github.com/Loop3D/plugin_loopstructural/commit/d231204b8fa6215c3a9cd2cac76c75b46bd3d183))
* add qgistogeodataframe ([5d6949b](https://github.com/Loop3D/plugin_loopstructural/commit/5d6949be4d2bff4d3e23fd85a643d795d7b91edc))
* add setter/getter for name field to prevent name not being a string ([ba95b0e](https://github.com/Loop3D/plugin_loopstructural/commit/ba95b0e32534b44c2c38c86b815c669eccc1498f))
* add stratgiraphic column to model when building stratigraphy ([393e343](https://github.com/Loop3D/plugin_loopstructural/commit/393e343439cfb53aaf3679831d38ccae621a64f2))
* add structural data to unit ([fd6f4d7](https://github.com/Loop3D/plugin_loopstructural/commit/fd6f4d750e7212c42ddeab6630777878eca20f1c))
* add unit to gui without creating a new one ([00c4d31](https://github.com/Loop3D/plugin_loopstructural/commit/00c4d314312e9592e5985c4b9c3ad1da663e80a1))
* add uuid to dictionary for created units ([d91a90c](https://github.com/Loop3D/plugin_loopstructural/commit/d91a90c247ad270cfbf74effade2e00fcf3cd2f1))
* adding checks to make sure the fields are not none and are in the layer ([1b0014b](https://github.com/Loop3D/plugin_loopstructural/commit/1b0014b7a81ef8534368815663991139e22970ad))
* adding new dock widget for 3D viewer ([b7a6d4e](https://github.com/Loop3D/plugin_loopstructural/commit/b7a6d4edfafeba1aeb5bccc250fdb59eb3315988))
* adding permission to linter ([ce3426b](https://github.com/Loop3D/plugin_loopstructural/commit/ce3426bbefea47e0f6a0b146c309a6eeb5d382b9))
* adding placeholder for default boundingbox. ([bf631a9](https://github.com/Loop3D/plugin_loopstructural/commit/bf631a9dcb75632c3ea8eb860de85261f67c6f66))
* adding placeholder to save object to file ([be06c6f](https://github.com/Loop3D/plugin_loopstructural/commit/be06c6f1dc0cebaa36ba7875afeadceb84f7ee2a))
* allow updating of stratigraphic column element ([12edfea](https://github.com/Loop3D/plugin_loopstructural/commit/12edfea2dcc1bc651745b0f9ee579b103b556263))
* allow z coordinate from shapefile to be used for elevation ([cea7d79](https://github.com/Loop3D/plugin_loopstructural/commit/cea7d794523cc9a08cc5d0b2786a112edb1edfaf))
* build stratigraphy objects ([54c3b16](https://github.com/Loop3D/plugin_loopstructural/commit/54c3b165f3146cbb68c018b8add723f0da3ecde9))
* call update stratirgaphy whenever column changes ([83effed](https://github.com/Loop3D/plugin_loopstructural/commit/83effed25c80bccfc122620cf39bdf07df053385))
* change interpolation weights to qdoublespinbox ([b64a2d6](https://github.com/Loop3D/plugin_loopstructural/commit/b64a2d6236f3161403cc984d51214548e7ccbe4a))
* connect orientation type toggle ([5bf2e66](https://github.com/Loop3D/plugin_loopstructural/commit/5bf2e66ba73f59479d1c217a104bb0538783d840))
* different settings for structural frames ([0e8db15](https://github.com/Loop3D/plugin_loopstructural/commit/0e8db1502b91608f0693c5f931c8efc28cd49bbb))
* don't add fields that aren't in the fault layer ([82708dd](https://github.com/Loop3D/plugin_loopstructural/commit/82708ddd799456b386d9ea4278164b4c77f4605e))
* don't add unconformities to feature list ([8bf531b](https://github.com/Loop3D/plugin_loopstructural/commit/8bf531b50ba72ba5dc2568e3221718dcd912302c))
* don't duplicate features in featurelist ([fc9685a](https://github.com/Loop3D/plugin_loopstructural/commit/fc9685abc16e2bb7c14317fd0047671e89393ab7))
* don't try and add scalarbar to the object list ([472ff09](https://github.com/Loop3D/plugin_loopstructural/commit/472ff09873144f1685827d6a0fda3801c9c55258))
* fault fault topology working ([996cdb8](https://github.com/Loop3D/plugin_loopstructural/commit/996cdb88a496bff7e32d9a942ef167c008f87736))
* fault topology plugged into LoopStructural classes with observer updates. ([377b39a](https://github.com/Loop3D/plugin_loopstructural/commit/377b39a9866f5675e8af8cec6d02557c450f6109))
* get displacement/dip/pitch from fault trace attributes ([819cea1](https://github.com/Loop3D/plugin_loopstructural/commit/819cea1918498c8f7920b7f707b1dbf58dd3a70f))
* ignore unconformities for feature settings... ([6705655](https://github.com/Loop3D/plugin_loopstructural/commit/6705655d401d0fa3540ad911498ebc0ad6aa7f6f))
* link feature to feature panel ([f925085](https://github.com/Loop3D/plugin_loopstructural/commit/f92508500e189cb0a3802f60a2ae329e4d17d952))
* link model manager and data manager ([863f970](https://github.com/Loop3D/plugin_loopstructural/commit/863f9700c90499ae5e3687231275a5a51c8dbcc4))
* make sure unit name is a string ([4c3fd30](https://github.com/Loop3D/plugin_loopstructural/commit/4c3fd30b0b3e32039668f257bc3103f50293dc66))
* model manager implementation for faults ([5a00032](https://github.com/Loop3D/plugin_loopstructural/commit/5a00032ece8995f1fa0de93ad047b17894a1ccea))
* move data/model manager to plugin main ([7a73327](https://github.com/Loop3D/plugin_loopstructural/commit/7a73327f33ecd53447c3d43f03e321189253ad58))
* nelements not n_elements ([e61e4e2](https://github.com/Loop3D/plugin_loopstructural/commit/e61e4e2cbf938dbddcc08344d293d815b239f15b))
* only show loopstructural warning messages ([ca87466](https://github.com/Loop3D/plugin_loopstructural/commit/ca87466299b204eab617e8d493f4611285ffbcdc))
* port to using stratigraphic column object from loopstructural ([a4689d6](https://github.com/Loop3D/plugin_loopstructural/commit/a4689d6227c2ce13663a25aef324c86444c92a45))
* put all loopstructural logs in 'LoopStructural' heading ([224a55e](https://github.com/Loop3D/plugin_loopstructural/commit/224a55e8592e8b287310b4a13042e364af59d75b))
* remove name string and colour button from stratigraphic unit ([606e3f4](https://github.com/Loop3D/plugin_loopstructural/commit/606e3f4d905544852a6edc1d5b5853adf13fa717))
* remove print statements and add default sampler output ([a391480](https://github.com/Loop3D/plugin_loopstructural/commit/a39148064c834f4868355b5a12a55f75af099466))
* remove unnecessary blank line in LoopstructuralPlugin class ([b00450d](https://github.com/Loop3D/plugin_loopstructural/commit/b00450d75569e417993b0197607db8ebe9b661a9))
* remove unused buttons ([7b036d5](https://github.com/Loop3D/plugin_loopstructural/commit/7b036d5200b81cb59f42622a5d76c9c6599410bd))
* remove unused imports and clean up code ([40fa142](https://github.com/Loop3D/plugin_loopstructural/commit/40fa1424aec3f6cb68a548b3666c477c1077496e))
* reorder import statements and improve error handling for dependencies ([6afc569](https://github.com/Loop3D/plugin_loopstructural/commit/6afc5692dbecf9cc8c2da1a0553e4a0a9266c48e))
* scale vector appropriate to model bb ([0b5a5fa](https://github.com/Loop3D/plugin_loopstructural/commit/0b5a5fa1329c35b2e7bc070d2814b7fc94a56bd0))
* set defaults for interpolator in qgs plugin ([61dd482](https://github.com/Loop3D/plugin_loopstructural/commit/61dd48222e0cf34523086f36225ec023a70a83e0))
* store reference to object instead of actor ([95a7b15](https://github.com/Loop3D/plugin_loopstructural/commit/95a7b15a60eb288f84862ea31c35d2ed6c939d66))
* stratigraphic column was reversed. ([604ca00](https://github.com/Loop3D/plugin_loopstructural/commit/604ca008ea4923b6280b8e2683d4c39336778e26))
* strike = dip_dir-90 ([f9c3efd](https://github.com/Loop3D/plugin_loopstructural/commit/f9c3efda141305934bbe7ee53b96e7d413c5e4c1))
* update bb nelements ([58e89ce](https://github.com/Loop3D/plugin_loopstructural/commit/58e89cececd71db3bb452314e313b481261f05e0))
* update data manager when fault layer changes ([64f0a29](https://github.com/Loop3D/plugin_loopstructural/commit/64f0a298707141afb84243dd47ff6b632b1d746c))
* update dem layer from project save ([58c25ed](https://github.com/Loop3D/plugin_loopstructural/commit/58c25ed3192acd2aa2ae261f3ebc3b513998dc31))
* update dependencies/add qpip ([41953ba](https://github.com/Loop3D/plugin_loopstructural/commit/41953bac1744cde03ca621c8765069a321822501))
* update fault when layer changes and remove faults when changing layers ([f22d286](https://github.com/Loop3D/plugin_loopstructural/commit/f22d286063f3db46e559cba5cc124162baed5d52))
* update requirements for LoopStructural ([6a138cf](https://github.com/Loop3D/plugin_loopstructural/commit/6a138cf9d7efbd67ec2010ec55b1563d5b67a9d8))
* update stratigraphic column units when thickness/name changes ([e180e9b](https://github.com/Loop3D/plugin_loopstructural/commit/e180e9b77a9ea528703d526d20984267890110df))
* use 3D extent for setting bounding box ([d25dced](https://github.com/Loop3D/plugin_loopstructural/commit/d25dcede918d9071804ba0e9b118a5ad74593f44))
* use default bb zmin/zmax ([a911bb9](https://github.com/Loop3D/plugin_loopstructural/commit/a911bb9c2c3b88b3beea783cb31be3ae1ab814b5))
* visualisation load external meshes ([a6fea12](https://github.com/Loop3D/plugin_loopstructural/commit/a6fea129ffdce7ec7f98c692ef3a704b699df12a))

## [0.1.6](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.5...v0.1.6) (2025-04-15)


### Bug Fixes

* bump ([465fc2e](https://github.com/Loop3D/plugin_loopstructural/commit/465fc2e74a2c7081247107bb7035b23b2276465a))

## [0.1.5](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.4...v0.1.5) (2025-04-15)


### Bug Fixes

* bump ([b860ff2](https://github.com/Loop3D/plugin_loopstructural/commit/b860ff2bd43e77d7da2a84c1076d13e558ba9264))

## [0.1.4](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.3...v0.1.4) (2025-04-15)


### Bug Fixes

* bump ([e3bedf4](https://github.com/Loop3D/plugin_loopstructural/commit/e3bedf41e38ba99d46b515d4cadae72107fe7b68))

## [0.1.3](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.2...v0.1.3) (2025-04-15)


### Bug Fixes

* increase max thickness ([3f628c5](https://github.com/Loop3D/plugin_loopstructural/commit/3f628c513be479d6d140ebcaf5825521ac26b9e1))
* stratigraphic column scope issues ([cfaf265](https://github.com/Loop3D/plugin_loopstructural/commit/cfaf265864fdd7b7a206270035e3895dae36e2be))

## [0.1.2](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.1...v0.1.2) (2025-04-04)


### Bug Fixes

* version bump ([88a8231](https://github.com/Loop3D/plugin_loopstructural/commit/88a82314da6fbb6a5f5ad334bff4156a7b3872c7))

## [0.1.1](https://github.com/Loop3D/plugin_loopstructural/compare/v0.1.0...v0.1.1) (2025-04-04)


### Bug Fixes

* add icon ([5da68ea](https://github.com/Loop3D/plugin_loopstructural/commit/5da68ea271ac8d3091c0936b2a30e8c3bbcb0100))
* adding pyvista viewer ([9be5a8d](https://github.com/Loop3D/plugin_loopstructural/commit/9be5a8dedc985050f2e408aee638c7d4c006b432))
* allow json serialisation + pass fault parameters correctly ([84a970a](https://github.com/Loop3D/plugin_loopstructural/commit/84a970a672704ff0e88ca7cc4e05c8a6a793ff59))
* cast fault name as string to avoid no points in fault error ([9ba7e69](https://github.com/Loop3D/plugin_loopstructural/commit/9ba7e690f6f155adf05f733f671858f1f07e0703))
* change icon path ([77eb53b](https://github.com/Loop3D/plugin_loopstructural/commit/77eb53be95ffab87e67e2a93afa828f5443c073d))
* change loopstructural to icon rather than menu bar. Make sure plugin is unloaded and plays nicely with other docks ([40552cb](https://github.com/Loop3D/plugin_loopstructural/commit/40552cb21a629488cde3e167eff7648d49620c55))
* dip dir strike-90 not +90 ([839dee3](https://github.com/Loop3D/plugin_loopstructural/commit/839dee385b2984eb53469938620222ca5320f509))
* downgrade warnings to info ([f48a9bd](https://github.com/Loop3D/plugin_loopstructural/commit/f48a9bd08e9cb81fc52444c8d6f9456261a15d6b))
* increase version compatibility to 3.28 ([e8d8a31](https://github.com/Loop3D/plugin_loopstructural/commit/e8d8a3157943a44c7e4441d76894b9a85be53777))
* passing colour from gui to strat column ([2e406e4](https://github.com/Loop3D/plugin_loopstructural/commit/2e406e4d34e6ac919b84cdb20a959036ea0d5d55))
* use qgs project to store model params. Update ([51ee5db](https://github.com/Loop3D/plugin_loopstructural/commit/51ee5db4e3640cadc421c4714ef58df7d38e7300))


### Documentation

* updating metadata urls ([7e65b8b](https://github.com/Loop3D/plugin_loopstructural/commit/7e65b8bb684f45d1657af59374c95cc2f135783e))

## 0.1.0 (2025-02-21)


### Bug Fixes

* bump version ([050947c](https://github.com/Loop3D/plugin_loopstructural/commit/050947ca6468291ef40c947893215c6f7eb0becc))
