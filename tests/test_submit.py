from api.models import UserProfile
from . import FixturedTestCase, TEST_USER_PASSWORD


class SubmitTestCase(FixturedTestCase):
    def test_set_default_compiler(self):
        user = self.newUser(username="leandro", is_active=True)
        self.updateUserProfile(user, compiler=self.cpp)

        self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )

        # Assert that the compiler is CPP
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.compiler.id, self.cpp.id)

        # Send a submit using python2
        self.client.post(
            "/submit/{}/".format(self.problem1.id),
            data={
                "source": "blah",
                "problem": self.problem1.id,
                "compiler": self.py2.id,
            },
        )

        # Assert that the compiler changed to python2
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.compiler.id, self.py2.id)
