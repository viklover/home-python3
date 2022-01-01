#include <ctime>
#include <cstdio>
#include <time.h>
#include <cstring>
#include <stdlib.h>
#include <iostream>
#include <sqlite3.h>

#include <vector>

using namespace std;

vector<string> objects = {};
unsigned short size = 0;

static int add_object(void *NotUsed, int argc, char **argv, char **azColName) 
{
    string name = string(argv[0]);

    if (name.find("hours") == string::npos) {
        return 0;
    }

    size_t mark = name.find("_", 0);

    //cout << name.substr(0, mark) << endl;

    objects.push_back(name.substr(0, mark));
    
    return 0;
}

bool is_exist = false;

static int callback(void *data, int argc, char **argv, char **azColName)
{
    is_exist = int(*argv[0]) != int('0');
    return 0;
}

struct tm* get_tm_date(long long timestamp)
{
    const time_t rawtime = (const time_t) timestamp;
    struct tm* dt;

    dt = localtime(&rawtime);

    return dt;
}

void print_output(string data) 
{
    freopen("data", "w", stdout);
    cout << data;
    fclose(stdout);
}

int main()
{
    sqlite3 *db;
    string request;

    bool was_error = false;

    string output;

    if (!sqlite3_open("../databases/stats", &db)) 
    {
        // GET ALL ID OBJECTS

        request = "SELECT name FROM sqlite_master WHERE type='table';";

        if (sqlite3_exec(db, request.c_str(), add_object, 0, 0) == SQLITE_OK) 
        {
            // GET START AND END DATE

            freopen("../bin/first_startup", "r", stdin);
            long long first_startup;
            cin >> first_startup;
            fclose(stdin);

            freopen("../bin/objects", "r", stdin);
            string objects_info;
            getline(cin, objects_info);
            fclose(stdin);
            cin.getline(0, 0);

            struct tm* start_date;
            start_date = get_tm_date(first_startup);

            time_t end = time(NULL);

            // START TASK

            output += "{";

            for (bool first = true; mktime(start_date) < end && !was_error; ++(*start_date).tm_mday, first = false)
            {
                char date[16];

                char day[16];
                char mon[16];
                char year[16];

                strftime(date, sizeof(date), "%d-%b-%Y", start_date);
                
                strftime(day, sizeof(day), "%d", start_date);
                strftime(mon, sizeof(mon), "%m", start_date);
                strftime(year, sizeof(year), "%Y", start_date);

                output += (!first ? ", " : "");
                output += "\""+string(date)+"\":";

                vector<string> ids = {};

                struct tm tm_date;

                if (!strptime(date, "%d-%b-%Y", &tm_date)) {
                    //cout << "ERROR" << endl;
                }

                for (unsigned short i = 0; i < objects.size(); ++i) 
                {

                    string object = objects[i];

                    if (objects_info.find(objects[i]) == string::npos) {
                        continue;
                    }
                    
                    size_t found_id = objects_info.find(object, 0);
                    size_t found_var = objects_info.find(string("\"was_created\":"), found_id);
                    size_t start_val = found_var+15;
                    size_t end_val = objects_info.find(string(","), start_val);
                    
                    long long was_created = stoll(objects_info.substr(start_val, end_val-start_val));
                    
                    if (was_created > ((long long) mktime(start_date))) {
                        continue;
                    }
                    
                    request = "SELECT EXISTS (SELECT \"date\" FROM \""+object+"_hours\" WHERE \"day\"=\""+to_string(stoi(day))+"\" AND \"month\"=\""+to_string(stoi(mon))+"\" AND \"year\"=\""+string(year)+"\");";

                    //cout << object << endl;
                    //cout << request << endl;
                    //cout << day << " " << mon << " " << year << endl;

                    if (sqlite3_exec(db, request.c_str(), callback, &object, 0) == SQLITE_OK) 
                    {
                        if (!is_exist) 
                        {
                            ids.push_back(object);
                        }
                    } 
                    else 
                    {
                        was_error = true;
                        break;
                    }
                }

                output += "[";

                for (unsigned short i = 0; i < ids.size(); ++i) 
                {
                    if (i > 0) {
                        output += ",";
                    }

                    output += "\""+string(ids[i])+"\"";
                }

                output += "]";
            }

            output += "}";

            if (!was_error) 
            {
                print_output(output);
            }
        }
        else
        {
            was_error = true;
        }
        sqlite3_close(db);
    } 
    else 
    {
       was_error = true;
    }

    if (was_error) 
    {
        print_output(string("{\"error\":\"hz\"}"));
    }

    return 0;
}
