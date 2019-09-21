/**
 Main JavaScript library for S4RiS StanD.
 Version: 1.9.1 - Presenter Mod.
 Author: Oleg "OSt" Strekalovsky.
 */

/**
 Information about problem submission.
 */
function RunInfo() {
    this.lastSubmitTime = 0;
    this.nTries = 0;
    this.solved = false;
    this.penalty = 0;
    this.defrost = false;
}

/**
 Problem.
 */
function Problem(letterName) {
    /**
     Name of the problem is his letter.
     */
    this.name = letterName;
}

/**
 Contestant submition.
 */
function Run(contestant, problem, time, success) {
    this.contestant = contestant;
    this.problem = problem;
    this.time = time;
    this.success = success;

    this.runsComparator = function (first, second) {
        return this.time - second.time;
    }
}

/**
 Contestant
 */
function Contestant(name) {
    this.name = name;
    this.runsList = new Array();
    /**
     Actual penalty.
     */
    this.penalty = 0;
    /**
     Actual amount of solved problems.
     */
    this.totalSolved = 0;
    /**
     Actual time of the last successful submission.
     */
    this.lastSuccessTime = 0;
    this.runInfoHash = {};
    this.place = 1;

    this.addRun = function (run) {
        this.runsList[this.runsList.length] = run;
    }

    this.getAllRuns = function () {
        return runsList;
    }

    /**
     Comparator for 2 contestant by ACM ICPC rule.
     */
    this.compareTo = function (second) {
        if (this.totalSolved == second.totalSolved) {
            if (this.penalty == second.penalty) {
                return this.lastSuccessTime - second.lastSuccessTime;
            } else {
                return this.penalty - second.penalty;
            }
        } else {
            return second.totalSolved - this.totalSolved;
        }
    }

    this.toString = function () {
        return name;
    }
}

/**
 Contest.
 */
function Contest(json, defrostingComparatorName) {
    this.inputLog = json;
    this.defrostingComparatorName = defrostingComparatorName;

    this.getContestName = function () {
        return this.inputLog.contestName;
    };

    this.getProblemsList = function () {
        return this.inputLog.problemLetters;
    };

    this.getTimeBeforeFreeze = function () {
        return this.inputLog.freezeTimeMinutesFromStart;
    };

    this.getContestantsJSONList = function () {
        return this.inputLog.contestants;
    };

    this.getRuns = function () {
        return this.inputLog.runs;
    };

    this.getContestants = function () {
        var contestantsHash = {};
        for (var idx in this.inputLog.contestants) {
            contestantsHash['' + this.inputLog.contestants[idx] + ''] = new Contestant(this.inputLog.contestants[idx]);
        }
        return contestantsHash;
    }

    this.getProblems = function () {
        var problemsHash = {};
        for (var idx in this.inputLog.problemLetters) {
            problemsHash['' + this.inputLog.problemLetters[idx] + ''] = new Problem(this.inputLog.problemLetters[idx]);
        }
        return problemsHash;
    }

    this.getRuns = function (cHash, pHash) {
        var runsList = new Array();
        for (var idx in this.inputLog.runs) {
            var contestant = cHash['' + this.inputLog.runs[idx].contestant + ''];
            var problem = pHash['' + this.inputLog.runs[idx].problemLetter + ''];
            var time = this.inputLog.runs[idx].timeMinutesFromStart;
            var success = this.inputLog.runs[idx].success;
            runsList[idx] = new Run(contestant, problem, time, success);
            cHash['' + contestant.name + ''].addRun(runsList[idx]);
        }
        return runsList;
    }

    this.createFrozenStandings = function () {
        var cHash = this.getContestants();
        var pHash = this.getProblems();
        var rList = this.getRuns(cHash, pHash);
        var limit = this.getTimeBeforeFreeze();
        var penalty = 20;
        for (var name in cHash) {
            var contestant = cHash[name];
            for (var probName in pHash) {
                contestant.runInfoHash[probName] = new RunInfo();
            }
            var curInfoHash = contestant.runInfoHash;
            for (var i = 0; i < cHash[name].runsList.length; i++) {
                var run = cHash[name].runsList[i];
                if (run.success && !curInfoHash[run.problem.name].solved) {
                    curInfoHash[run.problem.name].penalty = run.time + curInfoHash[run.problem.name].nTries * 20;
                    curInfoHash[run.problem.name].solved = true;
                    curInfoHash[run.problem.name].lastSubmitTime = run.time;
                    if (run.time < limit) {
                        contestant.penalty += curInfoHash[run.problem.name].penalty;
                        contestant.totalSolved++;
                        contestant.lastSuccessTime = Math.max(curInfoHash[run.problem.name].lastSubmitTime, contestant.lastSuccessTime);
                        curInfoHash[run.problem.name].defrost = true;
                    }
                } else if (!curInfoHash[run.problem.name].solved) {
                    curInfoHash[run.problem.name].nTries++;
                    curInfoHash[run.problem.name].lastSubmitTime = run.time;
                }
            }
        }
        var standings = new Standings(cHash, this.getTimeBeforeFreeze(), this.defrostingComparatorName);
        return standings;
    }
}

function Standings(cHash, limit, defrostingComparatorName) {

    this.limit = limit;

    /*
     * Comparator of contestant problems defrosting order by increasing last submit time.
     */
    this.ProblemDefrostingComparatorByLastSubmitTime = function (first, second) {
        return first.run.lastSubmitTime - second.run.lastSubmitTime;
    }

    /*
     * Comparator of contestant problems defrosting order by alphabetic problem name.
     */
    this.ProblemDefrostingComparatorByProblemName = function (first, second) {
        return first.problem.localeCompare(second.problem);
    }

    if (defrostingComparatorName == 'alphabeticProblemOrder') {
        this.ProblemDefrostingComparator = this.ProblemDefrostingComparatorByProblemName;
    } else if (defrostingComparatorName == 'increasingLastSubmitTime') {
        this.ProblemDefrostingComparator = this.ProblemDefrostingComparatorByLastSubmitTime;
    }


    this.ACMICPCComparator = function (first, second) {
        if (first.totalSolved == second.totalSolved) {
            if (first.penalty == second.penalty) {
                return first.lastSuccessTime - second.lastSuccessTime;
            } else {
                return first.penalty - second.penalty;
            }
        } else {
            return second.totalSolved - first.totalSolved;
        }
    }

    this.rankList = new Array();
    for (var name in cHash) {
        this.rankList[this.rankList.length] = cHash[name];
    }
    this.rankList.sort(this.ACMICPCComparator);

    this.get = function (idx) {
        return this.rankList[idx];
    }

    this.set = function (idx, contestant) {
        this.rankList[idx] = contestant;
    }

    this.size = function () {
        return this.rankList.length;
    }

    /**
     Current row in standings
     Zero indexing.
     */
    var curRow = this.rankList.length - 1;


    /**
     Current contestant index.
     */
    var curContestantIdx = 0;

    this.setCurRow = function (row) {
        curRow = row;
    }

    this.getCurRow = function () {
        return curRow;
    }

    /**
     Current row at frame.
     */
    var curFrameRow;

    this.setCurFrameRow = function (row) {
        curFrameRow = row;
    }

    this.getCurFrameRow = function () {
        return curFrameRow;
    }

    /**
     Current top row at frame.
     */
    var curTopRow = 0;

    this.setCurTopRow = function (row) {
        curTopRow = row;
    }

    this.getCurTopRow = function () {
        return curTopRow;
    }

    /**
     Update places in standings.
     */
    this.updatePlaces = function () {
        var place = 1;
        var size = this.size();
        for (var i = 0; i < size; i++) {
            if (i == 0) {
                this.get(i).place = place;
            } else {
                if (this.get(i).compareTo(this.get(i - 1)) == 0) {
                    this.get(i).place = this.get(i - 1).place;
                } else {
                    this.get(i).place = place;
                }
            }
            place++;

            setContestantPlace(i, this.get(i).place);
        }
    }

    /**
     Moves row up.
     */
    this.up = function (idx, contestant) {
        var save = idx;
        var nextPos = idx;
        for (; idx >= 1; idx--) {
            if (this.get(idx).compareTo(this.get(idx - 1)) >= 0) {
                break;
            } else if (this.get(idx).compareTo(this.get(idx - 1)) < 0) {
                nextPos = idx - 1;
                var buff = this.get(nextPos);
                this.set(nextPos, this.get(idx));
                this.set(idx, buff);
                getRow(nextPos).attr('id', -idx);
                getRow(idx).attr('id', nextPos);
                getRow(-idx).attr('id', idx);
            }
        }
        if (nextPos < save) {

            var delta = save - nextPos;
            moveRow(nextPos, delta);
            removeCurrentRow(nextPos);
            for (delta--; delta >= 0; delta--) {
                moveRow(save - delta, -1);
            }
        }
    }

    this.flashActive = false;

    /**
     Timer animation for blink.
     */
    this.timer;
    /**
     Problem name.
     */
    this.pName;

    this.curRunInfo;

    /**
     Process "Next Step".
     */
    this.goNext = function () {
        var contestant = this.get(curRow);
        setCurrentRow(curRow);
        if (this.flashActive) {
            this.flashActive = false;
            clearInterval(this.timer);
            if (this.curRunInfo.solved) {
                getRow(curRow).find('.problem').filter('#' + this.pName + '').find('.problem-result').animate({backgroundColor: '#669533'}, 100);
                updateAC(curRow, this.pName, this.curRunInfo.nTries);
                contestant.penalty += this.curRunInfo.penalty;
                updatePenalty(curRow, contestant.penalty);
                contestant.totalSolved++;
                contestant.lastSuccessTime = Math.max(this.curRunInfo.lastSubmitTime, contestant.lastSuccessTime);
                updateTotalSolved(curRow, contestant.totalSolved);
                this.up(curRow, contestant);
                this.updatePlaces();
                setCurrentRow(curRow);
                this.curRunInfo.defrost = true;
            } else {
                getRow(curRow).find('.problem').filter('#' + this.pName + '').find('.problem-result').animate({backgroundColor: '#C71C22'}, 100);
                updateNAC(curRow, this.pName, this.curRunInfo.nTries);
                this.curRunInfo.defrost = true;
            }
        } else {
            var tempProblemList = new Array();
            for (var pName in contestant.runInfoHash) {
                tempProblemList.push({run: contestant.runInfoHash[pName], problem: pName});
            }
            tempProblemList.sort(this.ProblemDefrostingComparator);
            for (var idx in tempProblemList) {
                var pName = tempProblemList[idx].problem;
                var runInfo = tempProblemList[idx].run;
                if ((runInfo.nTries > 0 || runInfo.solved) && !runInfo.defrost && runInfo.lastSubmitTime >= this.limit) {
                    this.flashActive = true;
                    this.pName = pName;
                    this.curRunInfo = runInfo;
                    var object = {
                        func: function () {
                            var elem = getRow(curRow).find('.problem').filter('#' + pName + '').find('.problem-result');
                            elem.animate({backgroundColor: '#FFFFFF'}, 400);
                            elem.animate({backgroundColor: '#FF9D00'}, 400);
                        }
                    }
                    this.timer = setInterval(object.func, 1000);
                    return;
                }
            }
            removeCurrentRow(curRow);
            if (curRow == 0) {
                removeCurrentRow(curRow);
                return;
            }
            curRow--;
            setCurrentRow(curRow);
            if (curFrameRow <= topLimit) {
                if (curRow < topLimit) {
                    curFrameRow--;
                } else {
                    curTopRow--;
                    setTopRow(curTopRow);
                }
            } else if (curFrameRow > topLimit) {
                curFrameRow--;
            }
        }
    }

    /**
     Process "Fast Next Step".
     No animation.
     Defrosting of the line stops when problems have ended or got AC.
     */
    this.goFFNext = function () {
        var contestant = this.get(curRow);
        setCurrentRow(curRow);
        var wasUp = false;
        var tempProblemList = new Array();
        for (var pName in contestant.runInfoHash) {
            tempProblemList.push({run: contestant.runInfoHash[pName], problem: pName});
        }
        tempProblemList.sort(this.ProblemDefrostingComparator);
        for (var idx in tempProblemList) {
            var pName = tempProblemList[idx].problem;
            var runInfo = tempProblemList[idx].run;
            if ((runInfo.nTries > 0 || runInfo.solved) && !runInfo.defrost && runInfo.lastSubmitTime >= this.limit) {
                this.pName = pName;
                this.curRunInfo = runInfo;
                if (this.curRunInfo.solved) {
                    updateAC(curRow, this.pName, this.curRunInfo.nTries);
                    contestant.penalty += this.curRunInfo.penalty;
                    updatePenalty(curRow, contestant.penalty);
                    contestant.totalSolved++;
                    contestant.lastSuccessTime = Math.max(this.curRunInfo.lastSubmitTime, contestant.lastSuccessTime);
                    updateTotalSolved(curRow, contestant.totalSolved);
                    wasUp = this.up(curRow, contestant);
                    this.updatePlaces();
                    setCurrentRow(curRow);
                    this.curRunInfo.defrost = true;
                    return;
                } else {
                    updateNAC(curRow, this.pName, this.curRunInfo.nTries);
                    wasUp = true;
                    this.curRunInfo.defrost = true;
                }
            }
        }
        if (!wasUp) {
            removeCurrentRow(curRow);
            if (curRow == 0) {
                removeCurrentRow(curRow);
                return;
            }
            curRow--;
            setCurrentRow(curRow);
            if (curFrameRow <= topLimit) {
                if (curRow < topLimit) {
                    curFrameRow--;
                } else {
                    curTopRow--;
                    setTopRow(curTopRow);
                }
            } else if (curFrameRow > topLimit) {
                curFrameRow--;
            }
        }
    }

    /**
     Move current row down and frameRow, if needed.
     */
    this.goBack = function () {
        if (curRow < this.size() - 1) {
            removeCurrentRow(curRow);
            curRow++;
            setCurrentRow(curRow);
            if (curFrameRow >= topLimit) {
                if (curRow > this.size() - (frameSize - topLimit)) {
                    curFrameRow++;
                } else {
                    curTopRow++;
                    setTopRow(curTopRow);
                }
            } else if (curFrameRow < topLimit) {
                curFrameRow++;
            }
        }
    }
}

function JSONLogPanelControl() {
    var $contestLogDiv = $('#contest-log');
    $contestLogDiv.fadeOut();
}

/**
 Append to the page a template of the contestant row.
 */
function createTemplateRow(idx) {
    $('#standings-table').append('<div class="element" id="' + idx + '" style=" z-index:0"><table class="contestant-info"><tr><td><div class="contestant"></div></td></tr><tr style="top 50px;"><td><table class="problems-list"><tr><td class="info"><div class="info-caption">' + L18n.autoTranslate("place") + '</div><div class="info-text" id="place">0</div></td><td class="problem"><div class="problem-caption">&nbsp;</div><div class="problem-result" id="no-submitions">.</div></td><td class="info"><div class="info-caption">' + L18n.autoTranslate("solvedProblems") + '</div><div class="info-text" id="totalSolved">0</div></td><td class="info"><div class="info-caption">' + L18n.autoTranslate("penalty") + '</div><div class="info-text" id="penalty">0</div></td></tr></table></td></tr></table></div>');
    $
};

/**
 Set problem names.
 Problem ID is its name.
 */
function fillProblemNames(problemsList) {
    $('.problem:last > .problem-caption').html(problemsList[0]);
    $('.problem:last').attr('id', problemsList[0]);
    for (var i = 1; i < problemsList.length; i++) {
        $('.problem:last').clone().insertAfter('.problem:last');
        $('.problem:last > .problem-caption').html(problemsList[i]);
        $('.problem:last').attr('id', problemsList[i]);
    }
}

/**
 Return jQuery object as a row for contestant by id.
 */
function getRow(idx) {
    return $('div .element ').filter('#' + idx + '');
}

/**
 Set contestant name.
 */
function setContestantName(idx, name) {
    getRow(idx).find('.contestant').html(name);
}

/**
 Set status "accepted" for problem to the contestant row.
 */
function updateAC(rowIdx, pName, nTries) {
    var res = nTries == 0 ? "+" : "+" + nTries + "";
    getRow(rowIdx).find('.problem').filter('#' + pName + '').find('.problem-result').attr('id', 'accepted');
    getRow(rowIdx).find('.problem').filter('#' + pName + '').find('.problem-result').html(res);
}

/**
 Set status "NotAccepted" for problem to the contestant row.
 */
function updateNAC(rowIdx, pName, nTries) {
    var res = "-" + nTries;
    getRow(rowIdx).find('.problem').filter('#' + pName + '').find('.problem-result').attr('id', 'not-accepted');
    getRow(rowIdx).find('.problem').filter('#' + pName + '').find('.problem-result').html(res);
}

/**
 Set penalty for row.
 */
function updatePenalty(rowIdx, penalty) {
    getRow(rowIdx).find('#penalty').html(penalty);
}

/**
 Set number of solved problems for contestant row.
 */
function updateTotalSolved(idx, totalSolved) {
    getRow(idx).find('#totalSolved').html(totalSolved);
}

/**
 Sets information for the participant attempts.
 */
function setContestantRunInfo(idx, contestant, limit) {
    var curInfoHash = contestant.runInfoHash;
    for (var pName in curInfoHash) {
        var infoRun = curInfoHash[pName];
        if (infoRun.lastSubmitTime < limit) {
            if (infoRun.solved) {
                updateAC(idx, pName, infoRun.nTries);
            } else if (infoRun.nTries > 0) {
                updateNAC(idx, pName, infoRun.nTries);
            }
        } else {
            // frozen result
            var res = "";
            if (infoRun.solved) {
                res = "?&nbsp;" + (infoRun.nTries + 1);
            } else {
                res = "?&nbsp;" + infoRun.nTries;
            }
            getRow(idx).find('.problem').filter('#' + pName + '').find('.problem-result').html(res);
            getRow(idx).find('.problem').filter('#' + pName + '').find('.problem-result').attr('id', 'unknown');
        }
    }
    updatePenalty(idx, contestant.penalty);
    updateTotalSolved(idx, contestant.totalSolved);
}

/**
 Sets the "place" for the line number idx.
 */
function setContestantPlace(idx, place) {
    getRow(idx).find('#place').html(place);
}

/**
 Set the color for "current row"
 */
function setCurrentRow(idx) {
    getRow(idx).find('.contestant-info').attr('id', 'selected-row');
}

/**
 Removes the color from the "current row".
 */
function removeCurrentRow(idx) {
    getRow(idx).find('.contestant-info').attr('id', '');
}

/**
 Sets the name of the contest.
 */
function setContestCaption(caption) {
    $('#contest-name').html(caption);
}

/**
 "Scrolling" of the results to the point where the string with number "idx" will be the top, if possible.
 */
function setTopRow(idx, speed, easing) {
    if (speed == undefined) {
        speed = 500;
    }
    if (easing == undefined) {
        easing = {easing: 'jswing'};
    }
    try {
        $('div#standings-table').scrollTo(getRow(idx).find('.contestant-info'), speed, easing);
    }
    catch (Exception) {}
}

/**
 Moves a row in a table on the delta positions up.
 */
function moveRow(idx, delta) {
    if (delta > 0) {
        getRow(idx).css('z-index', '1').animate({top: '-=' + (rowHeight * delta) + ''}, 2000, 'jswing', function () {
            getRow(idx).css('z-index', '0')
        });
    } else {
        getRow(idx).css('z-index', '-1').animate({top: '-=' + (rowHeight * delta) + ''}, 1500, 'jswing', function () {
        });
    }
}

/**
 Capable of displaying strings.
 */
var frameSize = 6;

/**
 The row number on which we will try to stay.
 */
var topLimit = 2;

/**
 * Row height.
 */
var rowHeight = 100;

/**
 Sets adaptive row height and total output space.
 */
function setAdaptiveSize(frameSize) {
    var browserWindow = $(window);
    var width = browserWindow.width();
    var height = browserWindow.height();
    var captionHeight = 50 + 20;
    var freeHeight = height - captionHeight;
    rowHeight = Math.floor(freeHeight / frameSize);
    $('#standings-table').height(rowHeight * frameSize);
}

/**
 Attempt to set adaptive layout for the row.
 //FIXME: Sometimes it's fail :(
 */
function setAdaptiveRow(rowHeight) {
    $('div .element').height(rowHeight);
    var contestantNameFontHeight = rowHeight * 1.2 / 100;
    $('.contestant').css('font-size', contestantNameFontHeight + 'em');
    var infoCaptionFontHeight = rowHeight * 1.2 / 100;
    var infoCaptionHeight = rowHeight * 20.0 / 100;
    $('.info-caption').css('font-size', infoCaptionFontHeight + 'em').height(infoCaptionHeight);
    var infoTextFontHeight = rowHeight * 1.2 / 100;
    $('.info-text').css('font-size', infoTextFontHeight + 'em');
    var problemCaptionFontHeight = rowHeight * 1.2 / 100;
    var problemCaptionHeight = rowHeight * 20.0 / 100;
    $('.problem-caption').css('font-size', problemCaptionFontHeight + 'em').height(problemCaptionHeight);
    var problemResultFontHeight = rowHeight * 1.0 / 100;
    var problemResultWidth = rowHeight * 50.0 / 100;
    $('.problem-result').css('font-size', problemResultFontHeight + 'em').width(problemResultWidth);
}

$('document').ready(function () {
    $('#inner #show-log').click(JSONLogPanelControl);
        try {
            var selectedFormat = $('.select-log').val();
            frameSize = $('.select-frameSize').val();
            topLimit = $('.select-currentRow').val();
            if (topLimit > frameSize - 1) {
                alert(L18n.autoTranslate("wrongInputCombination"));
                return;
            }
            var defrostingComparatorName = $('.select-defrosting-order').val();
            var contest;
            if (selectedFormat == 'stand') {
                var json = eval('(' + $('textarea').val() + ')');
                contest = new Contest(json, defrostingComparatorName);
            } else if (selectedFormat == 'ejudge') {
                var Log = new EJudgeConvertor($('textarea').val());
                contest = new Contest(Log.convert(), defrostingComparatorName);
            }

            var standings = contest.createFrozenStandings();
            var problemsHash = contest.getProblems();
            var limit = contest.getTimeBeforeFreeze();
            var problemsList = new Array();
            setContestCaption(contest.getContestName());
            for (var letter in problemsHash) {
                problemsList[problemsList.length] = problemsHash[letter].name;
            }
            problemsList.sort();
            var size = standings.size();
            setAdaptiveSize(frameSize);
            for (var i = 0; i < size; i++) {
                createTemplateRow(i);
                fillProblemNames(problemsList);
                setContestantName(i, standings.get(i).name);
                setContestantRunInfo(i, standings.get(i), limit);
            }
            setAdaptiveRow(rowHeight);
            standings.updatePlaces();
            // hide control panel
            JSONLogPanelControl();
            // go to the bottom of the table
            standings.setCurTopRow(size - frameSize);
            setTopRow(standings.getCurTopRow(), 4000, {easing: 'easeInQuad'});
            // setup current row
            standings.setCurRow(size - 1);
            standings.setCurFrameRow(frameSize - 1);
            setCurrentRow(standings.getCurRow());
            document.onkeydown = function (e) {
                if (e.which == 78) { // process "Next Step". Key "N".
                    standings.goNext();
                } else if (e.which == 70) { // process "Fast Next Step". Key "F".
                    standings.goFFNext();
                } else if (e.which == 34) { // process "Next Step". "Next button" on presenter or "Page Down" on keyboard
                    standings.goNext();
                } else if (e.which == 33) { // process "Fast Next Step". "Back button" on presenter or "Page Up" on keyboard.
                    standings.goFFNext();
                } else if (e.which == 66) { // move current row down. Key "B" on keyboard.
                    standings.goBack();
                }
            };
        } catch (Exception) {
            alert(L18n.autoTranslate("loadError"))
        }
});