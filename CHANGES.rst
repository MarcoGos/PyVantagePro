Changelog
---------

Version 0.3.12
~~~~~~~~~~~~~

Released on 2023-11-28

- Removed old setup files

Version 0.3.8
~~~~~~~~~~~~~

Released on 2023-11-10

- Added high/low values

Version 0.3.6
~~~~~~~~~~~~~

Released on 2023-11-05

- Added high/low times

Version 0.3.6
~~~~~~~~~~~~~

Released on 2023-11-05

- Fixed wind chill, dewpoint and heat index

Version 0.3.5
~~~~~~~~~~~~~

Released on 2023-11-05

- Added high/low values readout

Version 0.3.4
~~~~~~~~~~~~~

Released on 2023-11-05

- Fixed UV index and rain rate in archive data

Version 0.3.3
~~~~~~~~~~~~~

Released on 2023-10-31

- Fixed UV index in current data (was 10 times too high)
- Fixed value when TempOut was below 0°F

Version 0.3.2
~~~~~~~~~~~~~

Released on 2014-02-02.

- Added python3.3 and pypy support
- Use detox for parallel multienv tests
- Corrected WindAvgDir and WindHiDir
- Added one byte shift if wake-up is not working

Version 0.3.1
~~~~~~~~~~~~~

Released on 2012-06-28.

- remove duplicate records
- sort records by Datetime field


Version 0.3
~~~~~~~~~~~

Released on 2012-06-26.

- Use ordereddict to order data fields (Datetime field first)
- Fix a bug related to timeout
- Set timeout to 10 sec by default


Version 0.2
~~~~~~~~~~~

Released on 2012-06-20.

- Remove blist from requirements
- Minor bug fixes

Version 0.1
~~~~~~~~~~~

Released on 2012-06-14.

- First properly tagged release.
- Support VantagePro2 revB only.
- Parsing binary data into dict and list of dict.
- Command-line script.
