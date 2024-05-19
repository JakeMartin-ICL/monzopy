# read version from installed package
from importlib.metadata import version
__version__ = version(__name__)

# populate package namespace
from monzopy.monzopy import AbstractMonzoApi, AuthorisationExpiredError, InvalidMonzoAPIResponseError