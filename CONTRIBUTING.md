You are welcome to do PR to enhance TuyaMQTT. In general PR's should be targeted at the development or a feature branch.

Branch structure
----------------
```
master ---v1.1.0---------------------------|--v1.1.1--|--v1.2.0------->
              \        \----- hotfix -----/           /\
development ---\--v1.2.0--------------------|--------/  \-v1.3.0------>
                       \----- feature -----/
```

Branch names
-----------------
* `hotfix/<issue>`        In commit mention github issue number (eg #123)
* `feature/<enhancement>` In commit mention github issue number (eg #123)

Version numbers
-----------------
```
 +---------- Major: Can break compatibility
 | +-------- Minor: Enhancement of master, must be compatible 
 | |                with other versions within major version
 | | +------ Fix:   Bugfix on master branch
 | | |
v1.2.1
```


Code quality / enabling pre-commit hooks
-----------------
```bash
git clone https://github.com/<username>/tuyamqtt.git tuyamqtt_dev
cd tuyamqtt_dev
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install -r requirements_test.txt
pre-commit install
```

current commit
--------------
```bash
git log -n 1
```