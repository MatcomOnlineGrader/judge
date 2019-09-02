/**
 Localisation script for S4RiS StanD.
 Save with codepage UTF-8.
 */

function L18n() {

    /**
     JSON Object with all string constants in all languages.
     */
    var globalTranslations = {
        "ru": {
            "solvedProblems": "Задачи",
            "penalty": "Штраф",
            "place": "Место",
            "chooseLogFormat": "Выберите формат лога",
            "chooseFrameSize": "Выберите количество одновременно отображаемых участников",
            "chooseCurrentPos": "Выберите количество отображаемых участников, выше \"размораживаемого\"",
            "chooseDefrostingOrder": "Выберите порядок разморозки задач для участника",
            "alphabeticProblemOrder": "В алфавитном порядке",
            "increasingLastSubmitTime": "По возрастанию времени последнего сабмита участника по задаче",
            "insertLog": "Вставьте лог соревнования",
            "load": "Загрузить",
            "loadError": "Ошибка парсинга лога. Проверьте содержимое лога и выбранный формат",
            "wrongInputCombination": "Нельзя отобразить таблицу с таким количеством строк и количеством строк, выше \"размораживаемой\"",
            "control": "Управление:",
            "goNext": "N — выполнить следующий шаг \"разморозки\"",
            "goFastNext": "F — \"разморозить\" строку до первого AC без анимации",
            "goBack": "B — откатиться вниз по таблице",
            "recommendations": "Рекомендации по использованию:",
            "note1": "До демонстрации разморозки обязательно проверьте, что система выдаёт в конечном итоге те же результаты, что и ваша тестирующая система",
            "note2": "Крайне не желательно слишком быстро размораживать таблицу — это чревато появлением проблем с анимациями.<br/>Спокойно дождитесь окончания всех обновлений на странице после очередного нажатия клавиши",
            "note3": "Во время “быстрой разморозки” включите какую-нибудь ритмичную музыку, чтобы увеличить напряжение окружающих :)",
            "note4": "Для увеличения активной площади экрана включите \"полноэкранный режим\" в браузере",
            "note5": "Чем больше записей в логе соревнования — тем больше нагрузка на браузер и его JS движок. <br/>На слабых машинах и не последних версиях браузеров возможно падение скорости и плавности",
            "note6": "Если вас не устраивает внешний вид таблицы или принцип подсчёта результата соревнования — напишите мне и мы вместе решим ваши проблемы",
            "note7": "Если вы использовали данную программу на своём соревновании — напишите мне о вашем опыте работы с ней.<br/>Замечания и рекомендации приветствуются!",
            "authorInfo": "S4RiS StanD 1.9.1<br/><a href='https://github.com/OStrekalovsky/S4RiS-StanD'>Проект на GitHub</a>.<br/>Стрекаловский Олег (<a href=\'mailto: o.strekalovsky@yandex.ru\'>o.strekalovsky@yandex.ru</a>)"
        },
        "en": {
            "solvedProblems": "Problems",
            "penalty": "Penalty",
            "place": "Place",
            "chooseLogFormat": "Choose log format",
            "chooseFrameSize": "Select the number of participants simultaneously displayed",
            "chooseCurrentPos": "Select the number of participants displayed above \"unfreezes\"",
            "chooseDefrostingOrder": "Select the order of problems defrosting for contestant",
            "alphabeticProblemOrder": "By alphabetic order of problem name",
            "increasingLastSubmitTime": "By increasing contestant last submit time for problem",
            "insertLog": "Insert contest log",
            "load": "Load",
            "loadError": "Parse log error. Check the contents of the log and the chosen format",
            "wrongInputCombination": "Can not display a table of the number of rows and number of lines, up \"unfreezes\"",
            "control": "Control:",
            "goNext": "N — perform  next step of \"unfreeze\"",
            "goFastNext": "F — \"unfreeze\" row before first AC without animation",
            "goBack": "B — move down current row",
            "recommendations": "Tips to use:",
            "note1": "To demonstrate the defrost, sure to check that the system produces ultimately the same results as your testing system",
            "note2": "It's not advisable to defrost the table too quickly — it is fraught with the advent of stocks in the animations.<br/> Calmly wait until all the updates on the page after the next key press",
            "note3": "During the \"rapid unfreezing\" turn on some upbeat music to increase the stress of spectators :)",
            "note4": "To increase the active area of the screen, enable \"full screen\" in the browser",
            "note5": "More entries in the event log — greater load on the browser and it's Java Script engine.<br/> On slower machines and not the latest versions of browsers may drop the speed and smoothness",
            "note6": "If you do not like the look of the table or the principle of counting the results of contest and etc. - write to me and together we will solve your problems",
            "note7": "If you use this software on your competition - write to me about your experience with it.<br/> Comments and recommendations are welcome!",
            "authorInfo": "S4RiS StanD 1.9.1<br/><a href='https://github.com/OStrekalovsky/S4RiS-StanD'>GitHub project page</a>.<br/>Strekalovsky Oleg (<a href=\"mailto: o.strekalovsky@yandex.ru\">o.strekalovsky@yandex.ru</a>)"
        }
    }

    /**
     Return browser localse - "ru","en" etc.
     "en" by default.
     */
    this.getBrowserLang = function () {
        var lang = (navigator.language || navigator.systemLanguage || navigator.userLanguage || 'en').substr(0, 2).toLowerCase();
        return lang;
    }

    /**
     Return translation in browser language.
     */
    this.autoTranslate = function (phrase) {
        return this.translate(this.getBrowserLang(), phrase);
    }

    /**
     Return translation of prase in language lang.
     */
    this.translate = function (lang, phrase) {
        var language = globalTranslations[lang]
        if (language == undefined || language == null) {
            if (lang != "en") {
                return this.translate("en", phrase);
            } else {
                return "English translation not found";
            }
        }
        var translation = language[phrase];
        if (translation == undefined || translation == null) {
            return "No translation for phrase=" + phrase + " in language=" + lang;
        }
        return translation;
    }
}