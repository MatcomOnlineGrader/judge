/**
 JS библиотека для конвертора лога системы Ejudge в лог S4RiS StanD JSON.
 Подключается импортом в HTML файл.
 Автор: Стрекаловский О.А.
 Дата 25.06.2012.
*/

function EJudgeConvertor(xml){
   this.xml = xml;
   // пропускать ли ошибки компиляции.
   this.skipCompilationError = true;
   // непосредственно процедура конвертора
   this.convert = function(){
      var json = $.xml2json(xml);
      json.contestName = json.name;
      json.freezeTimeMinutesFromStart = (parseInt(json.duration)-parseInt(json.fog_time))/60;
      json.problemLetters = new Array();
      var nProblems = json.problems.problem.length;
      var problemHash={};
      for (var i = 0; i < nProblems; i++){
         json.problemLetters[i] = json.problems.problem[i].short_name;
         problemHash[''+json.problems.problem[i].id+''] = json.problems.problem[i].short_name;
      }
      delete json.sched_start_time;
      delete json.start_time;
      delete json.stop_time;
      delete json.unfog_time;
      json.contestants = new Array();
      var nUsers = json.users.user.length;
      var contestantHash={};
      for (var i = 0; i < nUsers; i++){
         json.contestants[i] = json.users.user[i].name;
         contestantHash[''+json.users.user[i].id+''] = json.users.user[i].name;
      }
      var nRuns = json.runs.run.length;
      json.tempRuns = new Array();
      for (var i = 0; i < nRuns; i++){
         if (json.runs.run[i].status!=='CE'){
            json.tempRuns[i] = new Object();
            json.tempRuns[i].contestant = contestantHash[''+json.runs.run[i].user_id+''];
            json.tempRuns[i].problemLetter = problemHash[''+json.runs.run[i].prob_id+''];
            json.tempRuns[i].timeMinutesFromStart =  ~~((parseInt(json.runs.run[i].time))/60);
            json.tempRuns[i].success = json.runs.run[i].status==='OK';
         }
      }
      json.runs = json.tempRuns;
      return json;
   };
}
