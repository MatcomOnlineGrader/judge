from .base import BaseGrader, GraderArguments, GraderResult
from .runexe import RunexeGrader
from .simple import SimpleGrader

GRADERS = {
    'runexe': RunexeGrader,
    'simple': SimpleGrader,
}
